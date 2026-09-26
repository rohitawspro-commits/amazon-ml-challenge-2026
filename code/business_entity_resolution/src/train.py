"""Train the matching model on a sample of Source-1 training entities.

Steps: normalise -> block (per country, forward and reverse) -> label from ground truth -> features
-> stage 1: LightGBM on the pair features, out-of-fold over the training queries
-> stage 2: LightGBM from the record's side (its best / second-best stage-1 probability, margins)
-> tune the decision threshold on a held-out validation split (macro F0.5 at precision >= --min-prec)
-> save artefacts. Candidates, features and stage-1 scores are cached per tag (--reuse-*), so a run resumes.
--block-only stops after blocking and its recall report (models/blocking_<tag>.json).
"""
import argparse
import json
import os
import time

import lightgbm as lgb
import numpy as np
import polars as pl

import stage2
from blocking import BLOCK_COLS, DEFAULT_CHANNELS, block_all, keep_depth, rev_channel_names
from common import MODELS, WORK, load_ground_truth, load_s1, load_sources, timer
from features import build_features_chunked, feature_names, fit_tfidf
from metrics import macro_f05, decide, search_threshold
from normalize import NORM_VERSION, normalize_frame


def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=200_000)
    ap.add_argument("--n-val", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--channels", default=None, help="JSON list of channel specs (default: blocking.DEFAULT_CHANNELS)")
    ap.add_argument("--rev-top-n", type=int, default=0,
                    help="reverse blocking: Source-1 entities kept per pool record, in every channel (0 = off)")
    ap.add_argument("--rev-depth", default="auto", help="keep reverse-only candidates up to this reverse rank; "
                    "'auto' = the smallest depth within --depth-tol of the full depth's recall (train split)")
    ap.add_argument("--depth-tol", type=float, default=0.0005)
    ap.add_argument("--rounds", type=int, default=3000)
    ap.add_argument("--lr", type=float, default=0.08)
    ap.add_argument("--folds", type=int, default=4, help="stage-1 out-of-fold folds over the training queries; "
                    "1 = a single stage-1 model and no stage 2")
    ap.add_argument("--min-prec", type=float, default=0.984, help="macro precision floor for the decision threshold")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--reuse-cand", action="store_true", help="reuse cached candidates (skip blocking)")
    ap.add_argument("--cand-tag", default=None, help="tag whose cached candidates to reuse (default: --tag)")
    ap.add_argument("--reuse-feats", action="store_true", help="reuse cached features of this tag")
    ap.add_argument("--reuse-stage1", action="store_true", help="reuse cached stage-1 scores and model of this tag")
    ap.add_argument("--block-only", action="store_true", help="stop after blocking and its recall report")
    args = ap.parse_args()
    args.channels = json.loads(args.channels) if args.channels else DEFAULT_CHANNELS
    if args.rev_top_n:
        args.channels = [dict(ch, rev_top_n=args.rev_top_n) for ch in args.channels]
    args.rev_depth = None if args.rev_depth in ("auto", "none") else int(args.rev_depth)
    args.auto_depth = args.rev_depth is None
    return args


def load_pool_normalised(split: str, columns=None) -> pl.DataFrame:
    """Normalised Source-2+3 pool (cached per normalisation version); `columns` limits what is loaded."""
    path = f"{WORK}/{split}_pool_norm_{NORM_VERSION}.parquet"
    if not os.path.exists(path):
        _, pool = load_sources(split)
        with timer(f"normalise {split} pool ({pool.height:,} rows)"):
            pool = normalize_frame(pool)
        pool.write_parquet(path)
        del pool
    return pl.read_parquet(path, columns=columns)


def load_s1_normalised(split: str) -> pl.DataFrame:
    """Whole normalised Source 1 (cached per normalisation version; predict.py caches test the same way)."""
    path = f"{WORK}/{split}_s1_norm_{NORM_VERSION}.parquet"
    if not os.path.exists(path):
        s1 = load_s1(split)
        with timer(f"normalise {split} S1 ({s1.height:,} rows)"):
            normalize_frame(s1).write_parquet(path)
    return pl.read_parquet(path)


BLOCK_LOAD_COLS = ["entity_id", "country"] + BLOCK_COLS


def blocking_report(cand: pl.DataFrame, truth_pairs: pl.DataFrame, cfg, n_q: int) -> dict:
    """Blocking recall and candidates per query on the train / val splits and overall: the forward channels
    alone, with the reverse candidates up to each depth (all reverse channels, then one at a time), and the
    reverse candidates alone ("reverse top-1 only" = how often a record's best entity is its true entity)."""
    names = [c["name"] for c in cfg.channels]
    rev = rev_channel_names(cfg.channels)
    fwd = pl.any_horizontal([pl.col(f"{n}_rank") < 99 for n in names])
    variants = {"forward": fwd}
    if rev:
        depth = max(c.get("rev_top_n", 0) for c in cfg.channels)
        ks = sorted({1, 2, 3, depth} & set(range(1, depth + 1)))
        for k in ks:
            variants[f"+reverse top-{k}"] = fwd | pl.any_horizontal([pl.col(f"{n}_rrank") < k for n in rev])
        for n in rev:
            variants[f"+reverse top-{depth} {n} only"] = fwd | (pl.col(f"{n}_rrank") < depth)
        for k in ks:
            variants[f"reverse top-{k} only"] = pl.any_horizontal([pl.col(f"{n}_rrank") < k for n in rev])
        for n in rev:
            variants[f"reverse top-1 {n} only"] = pl.col(f"{n}_rrank") < 1
    splits = {"all": (pl.lit(True), n_q), "train": (pl.col("q") < cfg.n_train, cfg.n_train),
              "val": (pl.col("q") >= cfg.n_train, n_q - cfg.n_train)}
    report = {}
    for s, (sel, nq) in splits.items():
        n_truth = truth_pairs.filter(sel).height
        c = cand.filter(sel)
        report[s] = {"queries": nq, "truth_pairs": n_truth}
        for v, keep in variants.items():
            k = c.filter(keep)
            report[s][v] = {"recall": int(k["label"].sum()) / max(n_truth, 1), "cand_per_query": k.height / max(nq, 1)}
            print(f"[blocking] {s:<5} {v:<28} recall={report[s][v]['recall']:.4f} "
                  f"cand/query={report[s][v]['cand_per_query']:.1f}", flush=True)
    return report


def choose_depth(report: dict, cfg) -> int:
    """Smallest reverse depth whose train-split recall is within --depth-tol of the full depth's."""
    depth = max(c.get("rev_top_n", 0) for c in cfg.channels)
    r = report["train"]
    full = r[f"+reverse top-{depth}"]["recall"]
    for k in range(1, depth + 1):
        key = f"+reverse top-{k}"
        if key in r and r[key]["recall"] >= full - cfg.depth_tol:
            return k
    return depth


def load_matrix(paths, cols, expr) -> np.ndarray:
    """Float32 feature matrix of the rows matching `expr`, filled file by file to bound the peak memory."""
    n = pl.scan_parquet(paths).filter(expr).select(pl.len()).collect().item()
    X = np.empty((n, len(cols)), dtype=np.float32)
    i = 0
    for path in paths:
        part = pl.scan_parquet(path).filter(expr).select([pl.col(c).cast(pl.Float32) for c in cols]).collect()
        if part.height:
            X[i:i + part.height] = part.to_numpy()
            i += part.height
    return X


def pick_threshold(rows, min_prec):
    """Best macro F0.5 among the grid rows (one_to_one, thr, f05, P, R) with macro precision >= min_prec;
    falls back to the most precise row if none reaches the floor."""
    ok = [r for r in rows if r[3] >= min_prec]
    return max(ok, key=lambda r: r[2]) if ok else max(rows, key=lambda r: r[3])


def evaluate(name, scored, truth, cfg, per_country=None):
    """Threshold search with the precision floor; prints and returns the chosen row and its metrics."""
    grid = np.arange(0.10, 0.96, 0.01)
    best, rows = search_threshold(scored, truth, grid)
    one, thr, f05, p, r = pick_threshold(rows, cfg.min_prec)
    m = macro_f05(decide(scored, thr, one), truth)
    print(f"[val] {name}: macro-F0.5={f05:.4f} P={p:.4f} R={r:.4f} @ thr={thr:.2f} one_to_one={one} "
          f"(precision floor {cfg.min_prec}) | unconstrained best F0.5={best[2]:.4f} @ thr={best[1]:.2f}", flush=True)
    for one_, thr_, f_, p_, r_ in rows:
        if abs(thr_ - thr) <= 0.03 and one_ == one:
            print(f"      thr={thr_:.2f} f05={f_:.4f} P={p_:.4f} R={r_:.4f}")
    out = {"threshold": thr, "one_to_one": one, "val_f05": f05, "val_metrics": m,
           "unconstrained": {"threshold": best[1], "one_to_one": best[0], "val_f05": best[2]}}
    if per_country is not None:
        pred = decide(scored, thr, one)
        out["per_country"] = {}
        for country in per_country["country"].unique().sort().to_list():
            t = truth.join(per_country.filter(pl.col("country") == country), on="q")
            mc = macro_f05(pred, t)
            out["per_country"][country] = mc
            print(f"      {country}: F0.5={mc['f05']:.4f} P={mc['prec_macro']:.4f} R={mc['rec_macro']:.4f} "
                  f"(n={t.height:,})")
    return out


def main():
    cfg = get_args()
    names = [c["name"] for c in cfg.channels]
    rev_names = rev_channel_names(cfg.channels)
    FEATURES = feature_names(names, rev_names)
    n_cpu = os.cpu_count()
    t0 = time.time()
    # reverse blocking searches the whole Source 1: normalise it all once (cached) and sample from it
    s1 = load_s1_normalised("train") if rev_names else load_s1("train")
    pool = load_pool_normalised("train", BLOCK_LOAD_COLS)  # light version for blocking
    gt = load_ground_truth()

    rng = np.random.default_rng(cfg.seed)
    idx = rng.permutation(s1.height)[: cfg.n_train + cfg.n_val]
    q = s1[idx].with_columns(pl.Series("split", ["train"] * cfg.n_train + ["val"] * (len(idx) - cfg.n_train)))
    if not rev_names:
        with timer(f"normalise {q.height:,} queries"):
            q = normalize_frame(q)
    u = None
    if rev_names:  # reverse-search universe; 'q' = the entity's row in the query sample, null if not sampled
        pos = np.full(s1.height, -1, dtype=np.int32)
        pos[idx] = np.arange(len(idx), dtype=np.int32)
        u = s1.select(["country"] + BLOCK_COLS).with_columns(q=pl.Series(pos)) \
            .with_columns(q=pl.when(pl.col("q") >= 0).then(pl.col("q")))
    del s1

    # labels: (q gidx, p gidx) pairs from ground truth restricted to sampled queries
    qid = q.select(pl.col("entity_id").alias("source1_entity_id"), pl.int_range(pl.len()).cast(pl.Int32).alias("q"))
    pid = pool.select(pl.col("entity_id").alias("p_id"), pl.int_range(pl.len()).cast(pl.Int32).alias("p"))
    truth_pairs = gt.join(qid, on="source1_entity_id").join(pid, on="p_id").select("q", "p")
    n_truth = truth_pairs.height

    cand_path = f"{WORK}/train_cand_{cfg.cand_tag or cfg.tag}.parquet"
    if cfg.reuse_cand and os.path.exists(cand_path):
        cand = pl.read_parquet(cand_path)
        print(f"[blocking] reusing {cand.height:,} cached candidates from {cand_path}", flush=True)
    else:
        with timer("blocking"):
            cand = block_all(q, pool, cfg.channels, out_prefix=f"{WORK}/train_block_{cfg.tag}", u_df=u)
        cand = cand.join(truth_pairs.with_columns(label=pl.lit(1, dtype=pl.Int8)), on=["q", "p"], how="left") \
            .with_columns(pl.col("label").fill_null(0))
        cand.write_parquet(cand_path)
    del pool, u
    found = int(cand["label"].sum())
    per_ch = " | ".join(f"{n}={int(cand.filter(pl.col(f'{n}_rank') < 99)['label'].sum()) / n_truth:.4f}" for n in names)
    print(f"[blocking] candidates={cand.height:,} ({cand.height / q.height:.1f}/query) | truth pairs={n_truth:,} "
          f"| recall={found / n_truth:.4f} | per channel: {per_ch}", flush=True)
    report = blocking_report(cand, truth_pairs, cfg, q.height)
    json.dump({"channels": cfg.channels, "sample": {"n_train": cfg.n_train, "n_val": cfg.n_val, "seed": cfg.seed},
               "report": report}, open(f"{MODELS}/blocking_{cfg.tag}.json", "w"), indent=1)
    if cfg.block_only:
        print(f"[done] total {time.time() - t0:.0f}s")
        return
    if rev_names:
        if cfg.auto_depth:
            cfg.rev_depth = choose_depth(report, cfg)
        cand = keep_depth(cand, cfg.channels, cfg.rev_depth)
        found = int(cand["label"].sum())
        print(f"[blocking] reverse depth {cfg.rev_depth}{' (auto)' if cfg.auto_depth else ''}: "
              f"candidates={cand.height:,} ({cand.height / q.height:.1f}/query) | recall={found / n_truth:.4f}", flush=True)
    n_cand = cand.height
    val_cand_per_q = cand.filter(pl.col("q") >= cfg.n_train).height / max(q.height - cfg.n_train, 1)

    # ---- features (cached per tag) ----
    feat_prefix = f"{WORK}/train_feats_{cfg.tag}"
    manifest = f"{feat_prefix}_manifest.json"
    if cfg.reuse_feats and os.path.exists(manifest):
        mf = json.load(open(manifest))
        assert mf["n_pairs"] == n_cand and mf["rev_depth"] == cfg.rev_depth, "cached features are of other candidates"
        paths = mf["paths"]
        print(f"[features] reusing {len(paths)} cached feature files", flush=True)
    else:
        pool = load_pool_normalised("train")  # full version for features
        with timer("tf-idf spaces"):
            tfidf = fit_tfidf(q, pool)
        with timer("features"):
            paths = build_features_chunked(cand, q, pool, names, tfidf, out_prefix=feat_prefix,
                                           log=lambda m: print(m, flush=True), rev_names=rev_names)
        json.dump({"paths": paths, "n_pairs": n_cand, "rev_depth": cfg.rev_depth}, open(manifest, "w"))
        del pool, tfidf
    del cand

    # queries 0..n_train-1 are the training split, the rest validation (see sampling above)
    lf = pl.scan_parquet(paths)
    is_tr = pl.col("q") < cfg.n_train
    tr = lf.filter(is_tr).select("q", "p", "label").collect()
    va = lf.filter(~is_tr).select("q", "p", "label").collect()
    y_tr, y_va = tr["label"].to_numpy(), va["label"].to_numpy()
    print(f"[data] train pairs={len(y_tr):,} (pos={y_tr.mean():.3f}) | val pairs={len(y_va):,}", flush=True)
    val_q = q.with_row_index("q").filter(pl.col("split") == "val").select(pl.col("q").cast(pl.Int32), "country")
    truth = val_q.select("q").join(truth_pairs.group_by("q").agg(pl.col("p").alias("truth")), on="q", how="left") \
        .with_columns(pl.col("truth").fill_null([]))

    # ---- stage 1: pairwise LightGBM, out-of-fold over the training queries ----
    params = dict(objective="binary", learning_rate=cfg.lr, num_leaves=127, min_data_in_leaf=100,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
                  verbose=-1, num_threads=n_cpu, seed=cfg.seed)
    stage1_path = f"{WORK}/train_stage1_{cfg.tag}.parquet"
    model_path = f"{MODELS}/lgb_{cfg.tag}.txt"
    if cfg.reuse_stage1 and os.path.exists(stage1_path) and os.path.exists(model_path):
        s1s = pl.read_parquet(stage1_path)
        model = lgb.Booster(model_file=model_path)
        best_iter, fold_iters = model.best_iteration or model.num_trees(), []
        print(f"[stage1] reusing cached scores {stage1_path} and model {model_path}", flush=True)
    else:
        with timer("load features"):
            X_va = load_matrix(paths, FEATURES, ~is_tr)
            X_tr = load_matrix(paths, FEATURES, is_tr)
        dtr = lgb.Dataset(X_tr, y_tr, feature_name=FEATURES, free_raw_data=False)
        dva = lgb.Dataset(X_va, y_va, reference=dtr, free_raw_data=False)
        fold_of_q = tr["q"].to_numpy() % max(cfg.folds, 1)  # queries are already a random permutation
        oof = np.full(len(y_tr), np.nan, dtype=np.float32)
        fold_iters = []
        if cfg.folds > 1:
            for k in range(cfg.folds):
                ho = fold_of_q == k
                with timer(f"stage 1 fold {k + 1}/{cfg.folds} ({int((~ho).sum()):,} train pairs)"):
                    mk = lgb.train(params, dtr.subset(np.flatnonzero(~ho)), num_boost_round=cfg.rounds, valid_sets=[dva],
                                   callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(500)])
                    oof[ho] = mk.predict(X_tr[ho], num_threads=n_cpu)
                fold_iters.append(mk.best_iteration)
                print(f"[stage1] fold {k + 1}: best_iteration={mk.best_iteration} val_logloss={mk.best_score['valid_0']['binary_logloss']:.5f}")
                del mk
        with timer(f"stage 1 full model ({len(y_tr):,} train pairs)"):
            model = lgb.train(params, dtr, num_boost_round=cfg.rounds, valid_sets=[dva],
                              callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(500)])
        best_iter = model.best_iteration
        model.save_model(model_path)
        imp = sorted(zip(FEATURES, model.feature_importance("gain")), key=lambda t: -t[1])
        print("[importance] " + ", ".join(f"{k}={v:.0f}" for k, v in imp[:30]))
        p1_va = model.predict(X_va, num_threads=n_cpu).astype(np.float32)
        s1s = pl.concat([tr.with_columns(prob=pl.Series(oof), split=pl.lit("train")),
                         va.with_columns(prob=pl.Series(p1_va), split=pl.lit("val"))])
        s1s.write_parquet(stage1_path)
        del X_tr, X_va, dtr, dva
    va_scored = s1s.filter(pl.col("split") == "val").select("q", "p", "prob")
    va_scored.write_parquet(f"{WORK}/val_scored1_{cfg.tag}.parquet")
    res1 = evaluate("stage 1", va_scored, truth, cfg, per_country=val_q)

    # ---- stage 2: the record's side, on out-of-fold stage-1 probabilities ----
    res2, model2 = None, None
    if cfg.folds > 1:
        pcols = stage2.pair_cols(rev_names)
        S2 = stage2.feature_names(rev_names)
        with timer("stage 2 features"):
            pairs = s1s.join(lf.select(["q", "p"] + pcols).collect(), on=["q", "p"], how="left")
            # record / query aggregates over the whole sample (train + val), so their density is uniform
            agg_p, agg_q = stage2.aggregates(pairs.select("q", "p", "prob"))
            f2 = stage2.build(pairs, agg_p, agg_q, rev_names)
            del pairs, agg_p, agg_q
        f2_tr, f2_va = f2.filter(pl.col("split") == "train"), f2.filter(pl.col("split") == "val")
        params2 = dict(objective="binary", learning_rate=0.05, num_leaves=63, min_data_in_leaf=200,
                       feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
                       verbose=-1, num_threads=n_cpu, seed=cfg.seed)
        with timer("stage 2 model"):
            d2 = lgb.Dataset(f2_tr.select(S2).to_numpy(), f2_tr["label"].to_numpy(), feature_name=S2)
            X2_va = f2_va.select(S2).to_numpy()
            d2v = lgb.Dataset(X2_va, f2_va["label"].to_numpy(), reference=d2)
            model2 = lgb.train(params2, d2, num_boost_round=2000, valid_sets=[d2v],
                               callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(200)])
        model2.save_model(f"{MODELS}/lgb2_{cfg.tag}.txt")
        imp2 = sorted(zip(S2, model2.feature_importance("gain")), key=lambda t: -t[1])
        print("[importance2] " + ", ".join(f"{k}={v:.0f}" for k, v in imp2))
        va_scored2 = f2_va.select("q", "p").with_columns(prob=pl.Series(model2.predict(X2_va, num_threads=n_cpu), dtype=pl.Float32))
        va_scored2.write_parquet(f"{WORK}/val_scored_{cfg.tag}.parquet")
        res2 = evaluate("stage 2", va_scored2, truth, cfg, per_country=val_q)
        del f2, f2_tr, f2_va, X2_va
    else:
        va_scored.write_parquet(f"{WORK}/val_scored_{cfg.tag}.parquet")

    final = res2 or res1
    v2 = f"{MODELS}/config_v2.json"
    if os.path.exists(v2):
        c2 = json.load(open(v2))
        m2 = c2["val_metrics"]
        print(f"[val] v2 baseline: macro-F0.5={m2['f05']:.4f} P={m2['prec_macro']:.4f} R={m2['rec_macro']:.4f} "
              f"cand/entity={c2['blocking']['cand_per_query']:.1f} | this run: macro-F0.5={final['val_f05']:.4f} P={final['val_metrics']['prec_macro']:.4f} "
              f"R={final['val_metrics']['rec_macro']:.4f} cand/entity={val_cand_per_q:.1f}", flush=True)
    conf = {"threshold": final["threshold"], "one_to_one": final["one_to_one"], "val_f05": final["val_f05"],
            "val_metrics": final["val_metrics"], "per_country": final.get("per_country"),
            "min_prec": cfg.min_prec, "stage1": res1,
            "sample": {"n_train": cfg.n_train, "n_val": cfg.n_val, "seed": cfg.seed},
            "blocking": {"channels": cfg.channels, "rev_depth": cfg.rev_depth, "recall": found / n_truth,
                         "cand_per_query": n_cand / q.height, "val_cand_per_query": val_cand_per_q,
                         "report": report},
            "features": FEATURES, "best_iteration": best_iter, "params": params,
            "folds": cfg.folds, "fold_iterations": fold_iters, "norm_version": NORM_VERSION}
    if model2 is not None:
        conf["stage2"] = {"features": stage2.feature_names(rev_names), "pair_cols": stage2.pair_cols(rev_names),
                          "best_iteration": model2.best_iteration, "params": params2}
    json.dump(conf, open(f"{MODELS}/config_{cfg.tag}.json", "w"), indent=1)
    print(f"[done] total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

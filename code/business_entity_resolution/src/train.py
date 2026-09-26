"""Train the matching model on a sample of Source-1 training entities.

Steps: normalise -> block (per country) -> label from ground truth -> features -> LightGBM
-> tune decision threshold on a held-out validation split (macro F0.5) -> save artefacts.
--block-only stops after blocking and its recall report (models/blocking_<tag>.json).
"""
import argparse
import json
import os
import time

import lightgbm as lgb
import numpy as np
import polars as pl

from blocking import BLOCK_COLS, DEFAULT_CHANNELS, block_all
from common import MODELS, WORK, load_ground_truth, load_s1, load_sources, timer
from features import build_features_chunked, feature_names, fit_tfidf
from metrics import search_threshold
from normalize import NORM_VERSION, normalize_frame


def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=200_000)
    ap.add_argument("--n-val", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--channels", default=None, help="JSON list of channel specs (default: blocking.DEFAULT_CHANNELS)")
    ap.add_argument("--rev-top-n", type=int, default=0,
                    help="reverse blocking: Source-1 entities kept per pool record, in every channel (0 = off)")
    ap.add_argument("--rounds", type=int, default=3000)
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--reuse-cand", action="store_true", help="reuse cached candidates (skip blocking)")
    ap.add_argument("--cand-tag", default=None, help="tag whose cached candidates to reuse (default: --tag)")
    ap.add_argument("--block-only", action="store_true", help="stop after blocking and its recall report")
    args = ap.parse_args()
    args.channels = json.loads(args.channels) if args.channels else DEFAULT_CHANNELS
    if args.rev_top_n:
        args.channels = [dict(ch, rev_top_n=args.rev_top_n) for ch in args.channels]
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
    alone, then with the reverse candidates up to each reverse depth (all channels, then one at a time)."""
    names = [c["name"] for c in cfg.channels]
    rev = [c["name"] for c in cfg.channels if c.get("rev_top_n", 0)]
    fwd = pl.any_horizontal([pl.col(f"{n}_rank") < 99 for n in names])
    variants = {"forward": fwd}
    if rev:
        depth = max(c.get("rev_top_n", 0) for c in cfg.channels)
        for k in sorted({1, 2, 3, depth} & set(range(1, depth + 1))):
            variants[f"+reverse top-{k}"] = fwd | pl.any_horizontal([pl.col(f"{n}_rrank") < k for n in rev])
        for n in rev:
            variants[f"+reverse top-{depth} {n} only"] = fwd | (pl.col(f"{n}_rrank") < depth)
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


def main():
    cfg = get_args()
    names = [c["name"] for c in cfg.channels]
    FEATURES = feature_names(names)
    t0 = time.time()
    # reverse blocking searches the whole Source 1: normalise it all once (cached) and sample from it
    reverse = any(c.get("rev_top_n", 0) for c in cfg.channels)
    s1 = load_s1_normalised("train") if reverse else load_s1("train")
    pool = load_pool_normalised("train", BLOCK_LOAD_COLS)  # light version for blocking
    gt = load_ground_truth()

    rng = np.random.default_rng(cfg.seed)
    idx = rng.permutation(s1.height)[: cfg.n_train + cfg.n_val]
    q = s1[idx].with_columns(pl.Series("split", ["train"] * cfg.n_train + ["val"] * (len(idx) - cfg.n_train)))
    if not reverse:
        with timer(f"normalise {q.height:,} queries"):
            q = normalize_frame(q)
    u = None
    if reverse:  # reverse-search universe; 'q' = the entity's row in the query sample, null if not sampled
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
    pool = load_pool_normalised("train")  # full version for features

    n_cand = cand.height
    with timer("tf-idf spaces"):
        tfidf = fit_tfidf(q, pool)
    with timer("features"):
        paths = build_features_chunked(cand, q, pool, names, tfidf, out_prefix=f"{WORK}/train_feats_{cfg.tag}",
                                       log=lambda m: print(m, flush=True))
    del pool, cand, tfidf
    # queries 0..n_train-1 are the training split, the rest validation (see sampling above)
    lf = pl.scan_parquet(paths)
    is_tr = pl.col("q") < cfg.n_train
    X_tr = lf.filter(is_tr).select(FEATURES).collect().to_numpy()
    y_tr = lf.filter(is_tr).select("label").collect()["label"].to_numpy()
    X_va = lf.filter(~is_tr).select(FEATURES).collect().to_numpy()
    va = lf.filter(~is_tr).select("q", "p", "label").collect()
    y_va = va["label"].to_numpy()
    print(f"[data] train pairs={len(y_tr):,} (pos={y_tr.mean():.3f}) | val pairs={len(y_va):,}", flush=True)

    params = dict(objective="binary", learning_rate=0.05, num_leaves=127, min_data_in_leaf=100,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
                  verbose=-1, num_threads=os.cpu_count(), seed=cfg.seed)
    with timer("lightgbm"):
        dtr = lgb.Dataset(X_tr, y_tr, feature_name=FEATURES)
        dva = lgb.Dataset(X_va, y_va, reference=dtr)
        model = lgb.train(params, dtr, num_boost_round=cfg.rounds, valid_sets=[dva],
                          callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)])
    model.save_model(f"{MODELS}/lgb_{cfg.tag}.txt")
    imp = sorted(zip(FEATURES, model.feature_importance("gain")), key=lambda t: -t[1])
    print("[importance] " + ", ".join(f"{k}={v:.0f}" for k, v in imp[:25]))

    # threshold search on validation (all val queries scored, including those with zero candidates)
    va_scored = va.select("q", "p").with_columns(prob=pl.Series(model.predict(X_va, num_threads=os.cpu_count())))
    val_q = q.with_row_index("q").filter(pl.col("split") == "val").select(pl.col("q").cast(pl.Int32))
    truth = val_q.join(truth_pairs.group_by("q").agg(pl.col("p").alias("truth")), on="q", how="left") \
        .with_columns(pl.col("truth").fill_null([]))
    va_scored.write_parquet(f"{WORK}/val_scored_{cfg.tag}.parquet")
    best, rows = search_threshold(va_scored, truth)
    one, thr, f05, m = best
    print(f"[val] best macro-F0.5={f05:.4f} @ thr={thr:.2f} one_to_one={one} | {m}")
    for one_, thr_, f_, p_, r_ in rows:
        if abs(thr_ - thr) <= 0.1 and one_ == one:
            print(f"      thr={thr_:.2f} f05={f_:.4f} P={p_:.4f} R={r_:.4f}")
    json.dump({"threshold": thr, "one_to_one": one, "val_f05": f05, "val_metrics": m,
               "sample": {"n_train": cfg.n_train, "n_val": cfg.n_val, "seed": cfg.seed},
               "blocking": {"channels": cfg.channels, "recall": found / n_truth, "cand_per_query": n_cand / q.height},
               "features": FEATURES, "best_iteration": model.best_iteration},
              open(f"{MODELS}/config_{cfg.tag}.json", "w"), indent=1)
    print(f"[done] total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

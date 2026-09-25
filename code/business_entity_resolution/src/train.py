"""Train the matching model on a sample of Source-1 training entities.

Steps: normalise -> block (per country) -> label from ground truth -> features -> LightGBM
-> tune decision threshold on a held-out validation split (macro F0.5) -> save artefacts.
"""
import argparse
import json
import os
import time

import lightgbm as lgb
import numpy as np
import polars as pl

from blocking import DEFAULT_CHANNELS, block_all
from common import MODELS, WORK, load_ground_truth, load_sources, timer
from features import build_features_chunked, feature_names
from metrics import search_threshold
from normalize import NORM_VERSION, normalize_frame


def get_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=200_000)
    ap.add_argument("--n-val", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--channels", default=None, help="JSON list of channel specs (default: blocking.DEFAULT_CHANNELS)")
    ap.add_argument("--rounds", type=int, default=2000)
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--reuse-cand", action="store_true", help="reuse cached candidates of this tag (skip blocking)")
    args = ap.parse_args()
    args.channels = json.loads(args.channels) if args.channels else DEFAULT_CHANNELS
    return args


def load_pool_normalised(split: str) -> pl.DataFrame:
    path = f"{WORK}/{split}_pool_norm_{NORM_VERSION}.parquet"
    if os.path.exists(path):
        return pl.read_parquet(path)
    _, pool = load_sources(split)
    with timer(f"normalise {split} pool ({pool.height:,} rows)"):
        pool = normalize_frame(pool)
    pool.write_parquet(path)
    return pool


def main():
    cfg = get_args()
    names = [c["name"] for c in cfg.channels]
    FEATURES = feature_names(names)
    t0 = time.time()
    s1, _ = load_sources("train")
    pool = load_pool_normalised("train")
    gt = load_ground_truth()

    rng = np.random.default_rng(cfg.seed)
    idx = rng.permutation(s1.height)[: cfg.n_train + cfg.n_val]
    q = s1[idx].with_columns(pl.Series("split", ["train"] * cfg.n_train + ["val"] * (len(idx) - cfg.n_train)))
    with timer(f"normalise {q.height:,} queries"):
        q = normalize_frame(q)

    # labels: (q gidx, p gidx) pairs from ground truth restricted to sampled queries
    qid = q.select(pl.col("entity_id").alias("source1_entity_id"), pl.int_range(pl.len()).cast(pl.Int32).alias("q"))
    pid = pool.select(pl.col("entity_id").alias("p_id"), pl.int_range(pl.len()).cast(pl.Int32).alias("p"))
    truth_pairs = gt.join(qid, on="source1_entity_id").join(pid, on="p_id").select("q", "p")
    n_truth = truth_pairs.height

    cand_path = f"{WORK}/train_cand_{cfg.tag}.parquet"
    if cfg.reuse_cand and os.path.exists(cand_path):
        cand = pl.read_parquet(cand_path)
        print(f"[blocking] reusing {cand.height:,} cached candidates from {cand_path}", flush=True)
    else:
        with timer("blocking"):
            cand = block_all(q, pool, cfg.channels)
        cand = cand.join(truth_pairs.with_columns(label=pl.lit(1, dtype=pl.Int8)), on=["q", "p"], how="left") \
            .with_columns(pl.col("label").fill_null(0))
        cand.write_parquet(cand_path)
    found = int(cand["label"].sum())
    per_ch = " | ".join(f"{n}={int(cand.filter(pl.col(f'{n}_rank') < 99)['label'].sum()) / n_truth:.4f}" for n in names)
    print(f"[blocking] candidates={cand.height:,} ({cand.height / q.height:.1f}/query) | truth pairs={n_truth:,} "
          f"| recall={found / n_truth:.4f} | per channel: {per_ch}", flush=True)

    with timer("features"):
        paths = build_features_chunked(cand, q, pool, names, out_prefix=f"{WORK}/train_feats_{cfg.tag}",
                                       log=lambda m: print(m, flush=True))
    del pool, cand
    split_df = q.select(pl.int_range(pl.len()).cast(pl.Int32).alias("q"), "split")
    feats = pl.read_parquet(paths).join(split_df, on="q")
    tr_mask = (feats["split"] == "train").to_numpy()
    y_all = feats["label"].to_numpy()
    X_all = feats.select(FEATURES).to_numpy()
    va = feats.filter(~pl.Series(tr_mask)).select("q", "p")
    del feats
    X_tr, y_tr = X_all[tr_mask], y_all[tr_mask]
    X_va, y_va = X_all[~tr_mask], y_all[~tr_mask]
    del X_all
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
    best, rows = search_threshold(va_scored, truth)
    one, thr, f05, m = best
    print(f"[val] best macro-F0.5={f05:.4f} @ thr={thr:.2f} one_to_one={one} | {m}")
    for one_, thr_, f_, p_, r_ in rows:
        if abs(thr_ - thr) <= 0.1 and one_ == one:
            print(f"      thr={thr_:.2f} f05={f_:.4f} P={p_:.4f} R={r_:.4f}")
    json.dump({"threshold": thr, "one_to_one": one, "val_f05": f05, "val_metrics": m,
               "sample": {"n_train": cfg.n_train, "n_val": cfg.n_val, "seed": cfg.seed},
               "blocking": {"channels": cfg.channels, "recall": found / n_truth, "cand_per_query": cand.height / q.height},
               "features": FEATURES, "best_iteration": model.best_iteration},
              open(f"{MODELS}/config_{cfg.tag}.json", "w"), indent=1)
    print(f"[done] total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

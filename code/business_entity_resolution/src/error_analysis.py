"""Inspect validation errors of a trained model: worst false merges and missed matches."""
import argparse
import json
import os

import lightgbm as lgb
import numpy as np
import polars as pl

from common import MODELS, WORK, load_sources
from metrics import decide, macro_f05
from train import load_pool_normalised


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--n", type=int, default=25)
    args = ap.parse_args()
    conf = json.load(open(f"{MODELS}/config_{args.tag}.json"))
    model = lgb.Booster(model_file=f"{MODELS}/lgb_{args.tag}.txt")
    smp = conf.get("sample", {"n_train": 200_000, "n_val": 50_000, "seed": 42})
    feats = pl.read_parquet(f"{WORK}/train_feats_{args.tag}_*.parquet").filter(pl.col("q") >= smp["n_train"])
    prob = model.predict(feats.select(conf["features"]).to_numpy(), num_threads=os.cpu_count())
    sc = feats.select("q", "p", "label").with_columns(prob=pl.Series(prob))

    s1, _ = load_sources("train")
    pool = load_pool_normalised("train")
    # rebuild the same query sample as train.py (same seed / sizes stored in the config? fall back to feats' q ids)
    q_ids = sorted(set(sc["q"].to_list()))
    pred = decide(sc, conf["threshold"], conf["one_to_one"])
    truth = sc.filter(pl.col("label") == 1).group_by("q").agg(pl.col("p").alias("truth"))
    allq = pl.DataFrame({"q": q_ids}).with_columns(pl.col("q").cast(pl.Int32)).join(truth, on="q", how="left") \
        .with_columns(pl.col("truth").fill_null([]))
    print("val (candidate-level truth) metrics:", macro_f05(pred, allq))

    fp = sc.filter((pl.col("label") == 0) & (pl.col("prob") >= conf["threshold"])).sort("prob", descending=True)
    fn = sc.filter((pl.col("label") == 1) & (pl.col("prob") < conf["threshold"])).sort("prob")
    print(f"\nfalse positives above threshold: {fp.height:,} | false negatives below: {fn.height:,}")
    # q indices refer to train.py's sampled frame: rebuild the identical sample (same seed / sizes)
    idx = np.random.default_rng(smp["seed"]).permutation(s1.height)[: smp["n_train"] + smp["n_val"]]
    qs = s1[idx]
    for title, df in (("FALSE POSITIVES (highest prob)", fp.head(args.n)), ("FALSE NEGATIVES (lowest prob)", fn.head(args.n))):
        print(f"\n=== {title} ===")
        for r in df.iter_rows(named=True):
            a = qs.row(r["q"], named=True)
            b = pool.row(r["p"], named=True)
            print(f"p={r['prob']:.3f} | S1: {a['business_name']} | {a['business_address']}")
            print(f"        -> {b['entity_id']}: {b['business_name']} | {b['business_address']}")


if __name__ == "__main__":
    main()

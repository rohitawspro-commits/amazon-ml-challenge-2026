"""Run the full pipeline on the test set and write output/matching_results.tsv + candidate_pairs.tsv."""
import argparse
import json
import os
import time

import lightgbm as lgb
import polars as pl

from blocking import block_all
from common import MODELS, OUT, WORK, load_s1, timer
from features import build_features, fit_tfidf
from metrics import decide
from normalize import NORM_VERSION, normalize_frame
from train import load_pool_normalised


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--cand-tag", default=None, help="reuse cached test candidates of another tag")
    ap.add_argument("--reblock", nargs="*", default=[], help="countries to re-block even when reusing candidates")
    ap.add_argument("--q-chunk", type=int, default=40_000, help="queries per feature/predict chunk")
    ap.add_argument("--threshold", type=float, default=None, help="override tuned threshold")
    args = ap.parse_args()
    t0 = time.time()

    conf = json.load(open(f"{MODELS}/config_{args.tag}.json"))
    channels = conf["blocking"]["channels"]
    names = [c["name"] for c in channels]
    FEATURES = conf["features"]
    thr = args.threshold if args.threshold is not None else conf["threshold"]
    model = lgb.Booster(model_file=f"{MODELS}/lgb_{args.tag}.txt")

    pool = load_pool_normalised("test")
    q_path = f"{WORK}/test_s1_norm_{NORM_VERSION}.parquet"
    if os.path.exists(q_path):
        q = pl.read_parquet(q_path)
    else:
        s1 = load_s1("test")
        with timer(f"normalise test S1 ({s1.height:,} rows)"):
            q = normalize_frame(s1)
        q.write_parquet(q_path)
        del s1

    cand_path = f"{WORK}/test_cand_{args.tag}.parquet"
    src_path = f"{WORK}/test_cand_{args.cand_tag}.parquet" if args.cand_tag else cand_path
    if os.path.exists(src_path):
        cand = pl.read_parquet(src_path)
        if args.reblock:
            q_country = q.select(pl.int_range(pl.len()).cast(pl.Int32).alias("q"), "country")
            keep = q_country.filter(~pl.col("country").is_in(args.reblock)).select("q")
            with timer(f"re-blocking {args.reblock}"):
                new = block_all(q, pool, channels, countries=args.reblock)
            cand = pl.concat([cand.join(keep, on="q"), new.select(cand.columns)]).sort(["q", "p"])
            cand.write_parquet(cand_path)
    else:
        with timer("blocking (test)"):
            cand = block_all(q, pool, channels)
        cand.write_parquet(cand_path)
    print(f"[blocking] {cand.height:,} candidate pairs ({cand.height / q.height:.1f}/query)", flush=True)

    with timer("tf-idf spaces"):
        tfidf = fit_tfidf(q, pool)
    scored = []
    n_q = q.height
    for start in range(0, n_q, args.q_chunk):
        part = cand.filter((pl.col("q") >= start) & (pl.col("q") < start + args.q_chunk))
        if part.height == 0:
            continue
        with timer(f"features+predict queries {start:,}-{min(start + args.q_chunk, n_q):,} ({part.height:,} pairs)"):
            feats = build_features(part, q, pool, names, tfidf)
            prob = model.predict(feats.select(FEATURES).to_numpy(), num_threads=os.cpu_count())
            scored.append(feats.select("q", "p").with_columns(prob=pl.Series(prob, dtype=pl.Float32)))
            del feats
    del tfidf
    scored = pl.concat(scored)
    scored.write_parquet(f"{WORK}/test_scored_{args.tag}.parquet")

    pred = decide(scored, thr, conf["one_to_one"])
    ids = pool.select(pl.int_range(pl.len()).cast(pl.Int32).alias("p"), pl.col("entity_id").alias("pid"))
    s1_ids = q.select(pl.int_range(pl.len()).cast(pl.Int32).alias("q"), pl.col("entity_id").alias("source1_entity_id"))

    def write_lists(pairs: pl.DataFrame, col: str, path: str):
        lists = pairs.join(ids, on="p").group_by("q").agg(pl.col("pid").str.join(",").alias(col))
        out = s1_ids.join(lists, on="q", how="left").sort("q").select("source1_entity_id", pl.col(col).fill_null(""))
        out.write_csv(path, separator="\t", quote_style="never")

    with timer("writing outputs"):
        write_lists(pred.explode("ids").rename({"ids": "p"}), "matched_entity_ids", f"{OUT}/matching_results.tsv")
        write_lists(cand.select("q", "p"), "candidate_entity_ids", f"{OUT}/candidate_pairs.tsv")
    matches = dict(zip(pred["q"].to_list(), pred["ids"].to_list()))
    n_match = sum(len(v) for v in matches.values())
    print(f"[output] threshold={thr:.2f} one_to_one={conf['one_to_one']} | S1 entities={n_q:,} | "
          f"with matches={len(matches):,} ({len(matches) / n_q:.3f}) | total matched ids={n_match:,} "
          f"({n_match / n_q:.2f}/entity) | total {time.time() - t0:.0f}s")
    per = q.select(pl.int_range(pl.len()).cast(pl.Int32).alias("q"), "country") \
        .join(pred.select("q", pl.col("ids").list.len().alias("n")), on="q", how="left").fill_null(0) \
        .group_by("country").agg(pl.len(), pl.col("n").mean().alias("matches_per_entity"),
                                 (pl.col("n") == 0).mean().alias("predicted_singleton_rate")).sort("country")
    print(f"[output] per country:\n{per}")


if __name__ == "__main__":
    main()

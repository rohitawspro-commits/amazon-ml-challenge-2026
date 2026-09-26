"""Run the full pipeline on the test set and write output/matching_results.tsv + candidate_pairs.tsv."""
import argparse
import gc
import glob
import json
import os
import time

import lightgbm as lgb
import numpy as np
import polars as pl

import stage2
from blocking import block_all, keep_depth, rev_channel_names
from common import MODELS, OUT, WORK, load_s1, timer
from features import build_features, fit_tfidf
from metrics import decide
from normalize import NORM_VERSION, normalize_frame
from train import BLOCK_LOAD_COLS, load_pool_normalised


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--cand-tag", default=None, help="reuse cached test candidates of another tag")
    ap.add_argument("--reblock", nargs="*", default=[], help="countries to re-block even when reusing candidates")
    ap.add_argument("--q-chunk", type=int, default=40_000, help="queries per feature/predict chunk")
    ap.add_argument("--threshold", type=float, default=None, help="override tuned threshold")
    ap.add_argument("--from-scores", action="store_true",
                    help="reuse the cached test scores of this tag and only rerun the decision and the output writing")
    args = ap.parse_args()
    t0 = time.time()
    n_cpu = os.cpu_count()

    conf = json.load(open(f"{MODELS}/config_{args.tag}.json"))
    channels = conf["blocking"]["channels"]
    names = [c["name"] for c in channels]
    rev_names = rev_channel_names(channels)
    rev_depth = conf["blocking"].get("rev_depth")
    FEATURES = conf["features"]
    thr = args.threshold if args.threshold is not None else conf["threshold"]
    model = lgb.Booster(model_file=f"{MODELS}/lgb_{args.tag}.txt")
    s2 = conf.get("stage2")
    model2 = lgb.Booster(model_file=f"{MODELS}/lgb2_{args.tag}.txt") if s2 else None

    pool = load_pool_normalised("test", BLOCK_LOAD_COLS)  # light version for blocking
    q_path = f"{WORK}/test_s1_norm_{NORM_VERSION}.parquet"
    if os.path.exists(q_path):
        q = pl.read_parquet(q_path)
    else:
        s1 = load_s1("test")
        with timer(f"normalise test S1 ({s1.height:,} rows)"):
            q = normalize_frame(s1)
        q.write_parquet(q_path)
        del s1

    # every test entity is a query, so the queries are also the universe of reverse blocking
    cand_path = f"{WORK}/test_cand_{args.tag}.parquet"
    src_path = f"{WORK}/test_cand_{args.cand_tag}.parquet" if args.cand_tag else cand_path
    if os.path.exists(src_path):
        cand = pl.read_parquet(src_path)
        if args.reblock:
            q_country = q.select(pl.int_range(pl.len()).cast(pl.Int32).alias("q"), "country")
            keep = q_country.filter(~pl.col("country").is_in(args.reblock)).select("q")
            with timer(f"re-blocking {args.reblock}"):
                new = block_all(q, pool, channels, countries=args.reblock, out_prefix=f"{WORK}/test_block_{args.tag}")
            cand = pl.concat([cand.join(keep, on="q"), new.select(cand.columns)]).sort(["q", "p"])
            cand.write_parquet(cand_path)
    else:
        with timer("blocking (test)"):
            cand = block_all(q, pool, channels, out_prefix=f"{WORK}/test_block_{args.tag}")
        cand.write_parquet(cand_path)
    cand = keep_depth(cand, channels, rev_depth)  # the cache keeps the full reverse depth
    print(f"[blocking] {cand.height:,} candidate pairs ({cand.height / q.height:.1f}/query)"
          + (f" at reverse depth {rev_depth}" if rev_names else ""), flush=True)
    del pool
    pool = load_pool_normalised("test")  # full version for features

    n_q = q.height
    scored_path = f"{WORK}/test_scored_{args.tag}.parquet"
    if args.from_scores and os.path.exists(scored_path):
        scored = pl.read_parquet(scored_path)
    else:
        with timer("tf-idf spaces"):
            tfidf = fit_tfidf(q, pool)
        # pass 1: pair features + stage-1 probability, one parquet per chunk of queries (with the pair columns
        # stage 2 reads back, since a record's candidates span many chunks)
        pcols = s2["pair_cols"] if s2 else []
        prefix = f"{WORK}/test_stage1_{args.tag}"
        for old in glob.glob(f"{prefix}_*.parquet"):
            os.remove(old)
        chunks = []
        for i, start in enumerate(range(0, n_q, args.q_chunk)):
            part = cand.filter((pl.col("q") >= start) & (pl.col("q") < start + args.q_chunk))
            if part.height == 0:
                continue
            with timer(f"features+predict queries {start:,}-{min(start + args.q_chunk, n_q):,} ({part.height:,} pairs)"):
                feats = build_features(part, q, pool, names, tfidf, rev_names)
                prob = model.predict(feats.select(FEATURES).to_numpy(), num_threads=n_cpu)
                path = f"{prefix}_{i:03d}.parquet"
                feats.select(["q", "p"] + pcols).with_columns(prob=pl.Series(prob, dtype=pl.Float32)).write_parquet(path)
                chunks.append(path)
                del feats
        del tfidf
        if s2:
            # pass 2: the record's side of the stage-1 probabilities, then the stage-2 model
            with timer("stage 2"):
                agg_p, agg_q = stage2.aggregates(pl.scan_parquet(chunks).select("q", "p", "prob").collect())
                scored = []
                for path in chunks:
                    f2 = stage2.build(pl.read_parquet(path), agg_p, agg_q, rev_names)
                    p2 = model2.predict(f2.select(s2["features"]).to_numpy(), num_threads=n_cpu)
                    scored.append(f2.select("q", "p", pl.col("prob").alias("prob1")).with_columns(prob=pl.Series(p2, dtype=pl.Float32)))
                    del f2
                scored = pl.concat(scored)
                del agg_p, agg_q
        else:
            scored = pl.scan_parquet(chunks).select("q", "p", "prob").collect()
        scored.write_parquet(scored_path)
    cand = cand.select("q", "p")

    pred = decide(scored.select("q", "p", "prob"), thr, conf["one_to_one"])
    ids = pool.select(pl.int_range(pl.len()).cast(pl.Int32).alias("p"), pl.col("entity_id").alias("pid"))
    s1_ids = q.select(pl.int_range(pl.len()).cast(pl.Int32).alias("q"), pl.col("entity_id").alias("source1_entity_id"))
    del scored, pool
    gc.collect()

    def write_lists(pairs: pl.DataFrame, col: str, path: str, chunk: int = 100_000):
        # Grouping all ~90M test candidate pairs in one go gets the process killed on a 15 GB machine.
        with open(path, "wb") as f:
            f.write(f"source1_entity_id\t{col}\n".encode())
            for start in range(0, n_q, chunk):
                part = pairs.filter((pl.col("q") >= start) & (pl.col("q") < start + chunk))
                lists = part.join(ids, on="p").group_by("q").agg(pl.col("pid").str.join(",").alias(col))
                out = s1_ids.slice(start, chunk).join(lists, on="q", how="left").sort("q") \
                    .select("source1_entity_id", pl.col(col).fill_null(""))
                out.write_csv(f, separator="\t", quote_style="never", include_header=False)

    with timer("writing outputs"):
        write_lists(pred.explode("ids").rename({"ids": "p"}), "matched_entity_ids", f"{OUT}/matching_results.tsv")
        write_lists(cand.select("q", "p"), "candidate_entity_ids", f"{OUT}/candidate_pairs.tsv")
    matches = dict(zip(pred["q"].to_list(), pred["ids"].to_list()))
    n_match = sum(len(v) for v in matches.values())
    print(f"[output] threshold={thr:.2f} one_to_one={conf['one_to_one']} | S1 entities={n_q:,} | "
          f"with matches={len(matches):,} ({len(matches) / n_q:.3f}) | total matched ids={n_match:,} "
          f"({n_match / n_q:.2f}/entity) | candidates={cand.height:,} ({cand.height / n_q:.1f}/entity) "
          f"| total {time.time() - t0:.0f}s")
    per = q.select(pl.int_range(pl.len()).cast(pl.Int32).alias("q"), "country") \
        .join(pred.select("q", pl.col("ids").list.len().alias("n")), on="q", how="left").fill_null(0) \
        .group_by("country").agg(pl.len(), pl.col("n").mean().alias("matches_per_entity"),
                                 (pl.col("n") == 0).mean().alias("predicted_singleton_rate")).sort("country")
    print(f"[output] per country:\n{per}")


if __name__ == "__main__":
    main()

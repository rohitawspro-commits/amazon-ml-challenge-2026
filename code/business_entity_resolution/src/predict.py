"""Run the full pipeline on the test set and write output/matching_results.tsv + candidate_pairs.tsv."""
import argparse
import json
import os
import time

import lightgbm as lgb
import polars as pl

from blocking import block_all
from common import MODELS, OUT, WORK, load_sources, timer
from features import build_features
from metrics import decide
from normalize import NORM_VERSION, normalize_frame
from train import load_pool_normalised


def write_id_lists(path, header, s1_ids, lists):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for sid in s1_ids:
            f.write(f"{sid}\t{','.join(lists.get(sid, ()))}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--cand-tag", default=None, help="reuse cached test candidates of another tag")
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

    s1, _ = load_sources("test")
    pool = load_pool_normalised("test")
    q_path = f"{WORK}/test_s1_norm_{NORM_VERSION}.parquet"
    if os.path.exists(q_path):
        q = pl.read_parquet(q_path)
    else:
        with timer(f"normalise test S1 ({s1.height:,} rows)"):
            q = normalize_frame(s1)
        q.write_parquet(q_path)

    cand_path = f"{WORK}/test_cand_{args.cand_tag or args.tag}.parquet"
    if os.path.exists(cand_path):
        cand = pl.read_parquet(cand_path)
    else:
        with timer("blocking (test)"):
            cand = block_all(q, pool, channels)
        cand.write_parquet(cand_path)
    print(f"[blocking] {cand.height:,} candidate pairs ({cand.height / q.height:.1f}/query)", flush=True)

    scored = []
    n_q = q.height
    for start in range(0, n_q, args.q_chunk):
        part = cand.filter((pl.col("q") >= start) & (pl.col("q") < start + args.q_chunk))
        if part.height == 0:
            continue
        with timer(f"features+predict queries {start:,}-{min(start + args.q_chunk, n_q):,} ({part.height:,} pairs)"):
            feats = build_features(part, q, pool, names)
            prob = model.predict(feats.select(FEATURES).cast(pl.Float32).to_numpy(), num_threads=os.cpu_count())
            scored.append(feats.select("q", "p").with_columns(prob=pl.Series(prob, dtype=pl.Float32)))
            del feats
    scored = pl.concat(scored)
    scored.write_parquet(f"{WORK}/test_scored_{args.tag}.parquet")

    pred = decide(scored, thr, conf["one_to_one"])
    pool_ids = pool["entity_id"].to_numpy()
    q_ids = q["entity_id"].to_list()
    matches = {q_ids[r["q"]]: [pool_ids[p] for p in r["ids"]] for r in pred.iter_rows(named=True)}
    cands = {q_ids[r["q"]]: [pool_ids[p] for p in r["p"]]
             for r in cand.group_by("q").agg(pl.col("p")).iter_rows(named=True)}
    with timer("writing outputs"):
        write_id_lists(f"{OUT}/matching_results.tsv", ["source1_entity_id", "matched_entity_ids"], q_ids, matches)
        write_id_lists(f"{OUT}/candidate_pairs.tsv", ["source1_entity_id", "candidate_entity_ids"], q_ids, cands)
    n_match = sum(len(v) for v in matches.values())
    print(f"[output] threshold={thr:.2f} one_to_one={conf['one_to_one']} | S1 entities={n_q:,} | "
          f"with matches={len(matches):,} ({len(matches) / n_q:.3f}) | total matched ids={n_match:,} "
          f"({n_match / n_q:.2f}/entity) | total {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()

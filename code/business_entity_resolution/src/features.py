"""Pairwise features for (Source-1 query, candidate) pairs."""
import numpy as np
import polars as pl
from rapidfuzz import fuzz, process
from rapidfuzz.distance import JaroWinkler

from common import N_THREADS

Q_COLS = ["nname", "core", "core_ns", "naddr", "nums"]
P_COLS = ["nname", "core", "core_ns", "naddr", "nums", "is_domain", "nonlatin", "addr_empty"]

_STRING_SCORERS = [
    ("name_ratio", "nname", fuzz.ratio),
    ("name_tsort", "nname", fuzz.token_sort_ratio),
    ("name_tset", "nname", fuzz.token_set_ratio),
    ("name_partial", "nname", fuzz.partial_ratio),
    ("core_ratio", "core", fuzz.ratio),
    ("core_tset", "core", fuzz.token_set_ratio),
    ("core_jw", "core", JaroWinkler.normalized_similarity),
    ("core_ns_ratio", "core_ns", fuzz.ratio),
    ("core_ns_partial", "core_ns", fuzz.partial_ratio),
    ("addr_ratio", "naddr", fuzz.ratio),
    ("addr_tsort", "naddr", fuzz.token_sort_ratio),
    ("addr_tset", "naddr", fuzz.token_set_ratio),
    ("addr_partial", "naddr", fuzz.partial_ratio),
]

GROUP_COLS = ["name_ratio", "core_tset", "core_jw", "addr_ratio", "addr_tset", "name_cos", "addr_cos", "combo"]

FEATURES = (
    [n for n, _, _ in _STRING_SCORERS]
    + ["name_cos", "name_rank", "addr_cos", "addr_rank", "in_both"]
    + ["core_jacc", "core_inter", "q_core_cov", "p_core_cov", "first_tok_eq", "any_tok_eq",
       "num_jacc", "num_inter", "house_eq", "q_nnum", "p_nnum",
       "addr_tok_jacc", "addr_tok_inter",
       "q_core_len", "p_core_len", "core_len_diff", "q_core_ntok", "p_core_ntok",
       "q_addr_len", "p_addr_len", "is_domain", "nonlatin", "addr_empty"]
    + [f"{c}_maxq" for c in GROUP_COLS] + [f"{c}_dmax" for c in GROUP_COLS]
    + ["n_cand_q", "combo_rank_q"]
)


def _tok(col):
    return pl.col(col).str.split(" ").list.eval(pl.element().filter(pl.element() != ""))


def build_features(cand: pl.DataFrame, q_df: pl.DataFrame, p_df: pl.DataFrame) -> pl.DataFrame:
    """cand has q/p global indices + blocking scores; q_df/p_df are the normalised frames."""
    qi = cand["q"].to_numpy()
    pi = cand["p"].to_numpy()
    qs = q_df.select(Q_COLS)[qi].rename({c: f"q_{c}" for c in Q_COLS})
    ps = p_df.select(P_COLS)[pi].rename({c: f"p_{c}" for c in P_COLS})
    df = pl.concat([cand, qs, ps], how="horizontal")

    # 1) string similarity scores (parallel C++ via rapidfuzz)
    new_cols = {}
    for name, col, scorer in _STRING_SCORERS:
        a = df[f"q_{col}"].to_list()
        b = df[f"p_{col}"].to_list()
        new_cols[name] = process.cpdist(a, b, scorer=scorer, workers=N_THREADS, dtype=np.float32)
    df = df.with_columns([pl.Series(k, v) for k, v in new_cols.items()])

    # 2) token / number set features (vectorised polars list ops)
    qc, pc = _tok("q_core"), _tok("p_core")
    qa, pa = _tok("q_naddr"), _tok("p_naddr")
    df = df.with_columns(
        core_inter=qc.list.set_intersection(pc).list.len().cast(pl.Float32),
        q_core_ntok=qc.list.len().cast(pl.Float32),
        p_core_ntok=pc.list.len().cast(pl.Float32),
        first_tok_eq=(qc.list.first() == pc.list.first()).cast(pl.Float32),
        num_inter=pl.col("q_nums").list.set_intersection(pl.col("p_nums")).list.len().cast(pl.Float32),
        q_nnum=pl.col("q_nums").list.len().cast(pl.Float32),
        p_nnum=pl.col("p_nums").list.len().cast(pl.Float32),
        house_eq=(pl.col("q_nums").list.first() == pl.col("p_nums").list.first()).cast(pl.Float32),
        addr_tok_inter=qa.list.set_intersection(pa).list.len().cast(pl.Float32),
        q_addr_ntok=qa.list.len().cast(pl.Float32),
        p_addr_ntok=pa.list.len().cast(pl.Float32),
        q_core_len=pl.col("q_core").str.len_chars().cast(pl.Float32),
        p_core_len=pl.col("p_core").str.len_chars().cast(pl.Float32),
        q_addr_len=pl.col("q_naddr").str.len_chars().cast(pl.Float32),
        p_addr_len=pl.col("p_naddr").str.len_chars().cast(pl.Float32),
        in_both=((pl.col("name_rank") < 99) & (pl.col("addr_rank") < 99)).cast(pl.Float32),
        is_domain=pl.col("p_is_domain").cast(pl.Float32),
        nonlatin=pl.col("p_nonlatin").cast(pl.Float32),
        addr_empty=pl.col("p_addr_empty").cast(pl.Float32),
    ).with_columns(
        core_jacc=pl.col("core_inter") / (pl.col("q_core_ntok") + pl.col("p_core_ntok") - pl.col("core_inter")).clip(1),
        q_core_cov=pl.col("core_inter") / pl.col("q_core_ntok").clip(1),
        p_core_cov=pl.col("core_inter") / pl.col("p_core_ntok").clip(1),
        any_tok_eq=(pl.col("core_inter") > 0).cast(pl.Float32),
        num_jacc=pl.col("num_inter") / (pl.col("q_nnum") + pl.col("p_nnum") - pl.col("num_inter")).clip(1),
        addr_tok_jacc=pl.col("addr_tok_inter") / (pl.col("q_addr_ntok") + pl.col("p_addr_ntok") - pl.col("addr_tok_inter")).clip(1),
        core_len_diff=(pl.col("q_core_len") - pl.col("p_core_len")).abs(),
        house_eq=pl.col("house_eq").fill_null(0.0),
        first_tok_eq=pl.col("first_tok_eq").fill_null(0.0),
        combo=(pl.col("core_tset") + pl.col("addr_tset")) / 200.0 + pl.col("name_cos") + pl.col("addr_cos"),
    )

    # 3) context features relative to the other candidates of the same query
    df = df.with_columns(
        [pl.col(c).max().over("q").alias(f"{c}_maxq") for c in GROUP_COLS]
        + [pl.len().over("q").cast(pl.Float32).alias("n_cand_q"),
           pl.col("combo").rank(method="ordinal", descending=True).over("q").cast(pl.Float32).alias("combo_rank_q")]
    ).with_columns([(pl.col(c) - pl.col(f"{c}_maxq")).alias(f"{c}_dmax") for c in GROUP_COLS])

    keep = ["q", "p"] + FEATURES
    return df.select(keep)

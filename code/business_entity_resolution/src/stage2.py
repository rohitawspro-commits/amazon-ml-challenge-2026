"""Stage 2: decide from the record's side.

Every Source-2/3 record belongs to at most one Source-1 entity, and a true copy is very similar to its
own entity. After the first (pairwise) LightGBM pass, each pair is therefore re-scored with the record's
view of its candidate entities: the record's best and second-best stage-1 probability, the margin of this
pair over the record's strongest other entity, whether this entity is the record's top choice, and the
same quantities from the entity's side (its best / second-best record, how many records it seems to
have). The reverse-blocking margins (cosine gap over the whole Source 1) and a few pair features come
along so the model can tell "clearly preferred" from "split between two entities".

At training time the stage-1 probabilities are out-of-fold, so stage 2 never sees in-sample scores.
"""
import polars as pl

# per-pair inputs taken from the stage-1 feature table (besides the reverse-blocking features)
PAIR_COLS = ["house_eq", "house_conflict", "addr_empty", "core_tset", "addr_tset", "n_hit", "n_cand_q"]
AGG_COLS = ["prob", "p_best", "p_2nd", "p_margin", "p_is_top", "q_best", "q_2nd", "q_margin", "q_n_hi", "q_sum"]


def pair_cols(rev_names):
    """Stage-1 feature columns that stage 2 reads back per pair."""
    rev = [f"{n}_{s}" for n in rev_names for s in ("rtop", "rgap", "rdiff")]
    return PAIR_COLS + rev + (["n_rtop"] if rev_names else [])


def feature_names(rev_names):
    return AGG_COLS + pair_cols(rev_names)


def aggregates(scored: pl.DataFrame):
    """Per-record and per-query views of the stage-1 probabilities. scored: q, p, prob (all candidate pairs)."""
    top2 = pl.col("prob").top_k(2)
    agg_p = scored.group_by("p").agg(top2.alias("t")).select(
        "p", pl.col("t").list.get(0).alias("p_best"), pl.col("t").list.get(1, null_on_oob=True).fill_null(0.0).alias("p_2nd"))
    agg_q = scored.group_by("q").agg(
        top2.alias("t"), (pl.col("prob") >= 0.5).sum().cast(pl.Float32).alias("q_n_hi"),
        pl.col("prob").sum().cast(pl.Float32).alias("q_sum"),
    ).select("q", pl.col("t").list.get(0).alias("q_best"), pl.col("t").list.get(1, null_on_oob=True).fill_null(0.0).alias("q_2nd"),
             "q_n_hi", "q_sum")
    return agg_p, agg_q


def build(df: pl.DataFrame, agg_p: pl.DataFrame, agg_q: pl.DataFrame, rev_names) -> pl.DataFrame:
    """Stage-2 feature frame for pairs df (q, p, prob + pair_cols(rev_names)); other columns are kept."""
    out = df.join(agg_p, on="p", how="left").join(agg_q, on="q", how="left")
    p_top = pl.col("prob") >= pl.col("p_best")
    q_top = pl.col("prob") >= pl.col("q_best")
    return out.with_columns(
        # margin over the strongest OTHER entity of this record / OTHER record of this entity
        p_margin=pl.col("prob") - pl.when(p_top).then(pl.col("p_2nd")).otherwise(pl.col("p_best")),
        q_margin=pl.col("prob") - pl.when(q_top).then(pl.col("q_2nd")).otherwise(pl.col("q_best")),
        p_is_top=p_top.cast(pl.Float32),
    ).with_columns([pl.col(c).cast(pl.Float32) for c in feature_names(rev_names)])

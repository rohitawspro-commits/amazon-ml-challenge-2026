"""Macro F0.5 scoring, decision rules (threshold + one-to-one assignment) and threshold search."""
import numpy as np
import polars as pl


def macro_f05(pred: pl.DataFrame, truth: pl.DataFrame) -> dict:
    """pred / truth: one row per query with a list column 'ids' (pred) / 'truth' (truth).

    Every query in `truth` is scored (queries missing from `pred` count as empty predictions).
    """
    df = truth.join(pred, on="q", how="left").with_columns(
        pl.col("ids").fill_null([]),
    ).with_columns(
        tp=pl.col("ids").list.set_intersection(pl.col("truth")).list.len().cast(pl.Float64),
        npred=pl.col("ids").list.len().cast(pl.Float64),
        ntrue=pl.col("truth").list.len().cast(pl.Float64),
    ).with_columns(
        prec=pl.when(pl.col("npred") > 0).then(pl.col("tp") / pl.col("npred")).otherwise(0.0),
        rec=pl.when(pl.col("ntrue") > 0).then(pl.col("tp") / pl.col("ntrue")).otherwise(0.0),
    ).with_columns(
        f=pl.when((pl.col("ntrue") == 0) & (pl.col("npred") == 0)).then(1.0)
        .when((pl.col("ntrue") == 0) | (pl.col("npred") == 0)).then(0.0)
        .otherwise(1.25 * pl.col("prec") * pl.col("rec") / (0.25 * pl.col("prec") + pl.col("rec")).clip(1e-9))
    )
    return {
        "f05": float(df["f"].mean()),
        "prec_macro": float(df.filter(pl.col("ntrue") > 0)["prec"].mean()),
        "rec_macro": float(df.filter(pl.col("ntrue") > 0)["rec"].mean()),
        "singleton_acc": float(df.filter(pl.col("ntrue") == 0).select((pl.col("npred") == 0).cast(pl.Float64).mean()).item())
        if (df["ntrue"] == 0).any() else float("nan"),
        "pair_precision": float(df["tp"].sum() / max(df["npred"].sum(), 1)),
        "pair_recall": float(df["tp"].sum() / max(df["ntrue"].sum(), 1)),
    }


def decide(scored: pl.DataFrame, thr: float, one_to_one: bool = True) -> pl.DataFrame:
    """Turn scored candidate pairs (q, p, prob) into predictions: list of p per q."""
    d = scored.filter(pl.col("prob") >= thr)
    if one_to_one:  # Source 1 is deduplicated: a pool record can belong to at most one S1 entity
        d = d.sort("prob", descending=True).unique(subset=["p"], keep="first", maintain_order=True)
    return d.group_by("q").agg(pl.col("p").alias("ids"))


def search_threshold(scored: pl.DataFrame, truth: pl.DataFrame, grid=None):
    """Grid-search the probability threshold (with and without one-to-one) for macro F0.5."""
    grid = np.arange(0.20, 0.96, 0.02) if grid is None else grid
    best = None
    rows = []
    for one in (True, False):
        for thr in grid:
            m = macro_f05(decide(scored, float(thr), one), truth)
            rows.append((one, float(thr), m["f05"], m["prec_macro"], m["rec_macro"]))
            if best is None or m["f05"] > best[2]:
                best = (one, float(thr), m["f05"], m)
    return best, rows

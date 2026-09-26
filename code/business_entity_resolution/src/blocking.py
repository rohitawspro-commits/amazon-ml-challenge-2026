"""Candidate generation (blocking).

Several independent retrieval channels per country, results unioned. A channel is a TF-IDF
vector space (word tokens or character n-grams) over one normalised text column; for every
Source-1 query it keeps the top-N most similar pool records by cosine (sparse_dot_topn).
Frequent terms are pruned with `max_df`, which is what keeps the sparse products fast.
Each country's candidates are written to parquet as soon as they are ready, so the peak
memory is that of one country's channels, not of the whole test set.
"""
import os

import numpy as np
import polars as pl
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sparse_dot_topn import sp_matmul_topn

from common import N_THREADS, timer

# name: short id used as feature prefix; col: normalised text column; analyzer/ngram: TF-IDF space.
DEFAULT_CHANNELS = [
    {"name": "w", "col": "both", "analyzer": "word", "ngram": [1, 1], "max_df": 0.02, "top_n": 40, "thr": 0.05},
    {"name": "n3", "col": "core", "analyzer": "char_wb", "ngram": [3, 3], "max_df": 0.01, "top_n": 10, "thr": 0.10},
    {"name": "a4", "col": "naddr", "analyzer": "char_wb", "ngram": [4, 4], "max_df": 0.01, "top_n": 15, "thr": 0.10},
]
BLOCK_COLS = ["core", "naddr", "both"]


def _topn_channel(queries, docs, ch, q_chunk=150_000):
    """Top-N cosine neighbours of every query among docs. Returns (q, p, cos, rank) frame."""
    kw = dict(analyzer=ch["analyzer"], min_df=2, max_df=ch["max_df"], dtype=np.float32, sublinear_tf=True)
    if ch["analyzer"] == "word":
        kw["token_pattern"] = r"\S+"
    else:
        kw["ngram_range"] = tuple(ch["ngram"])
    vec = TfidfVectorizer(**kw)
    P = vec.fit_transform(docs)
    PT = sparse.csr_matrix(P.T)
    del P
    parts = []
    for start in range(0, len(queries), q_chunk):
        Q = vec.transform(queries[start:start + q_chunk])
        C = sparse.csr_matrix(sp_matmul_topn(Q, PT, top_n=ch["top_n"], threshold=ch["thr"], sort=True, n_threads=N_THREADS))
        counts = np.diff(C.indptr)
        rows = np.repeat(np.arange(C.shape[0], dtype=np.int64), counts) + start
        rank = np.arange(len(C.indices)) - np.repeat(C.indptr[:-1], counts)
        parts.append(pl.DataFrame({
            "q": rows.astype(np.int32), "p": C.indices.astype(np.int32),
            "cos": C.data.astype(np.float32), "rank": rank.astype(np.int8),
        }))
    empty = pl.DataFrame(schema={"q": pl.Int32, "p": pl.Int32, "cos": pl.Float32, "rank": pl.Int8})
    return pl.concat(parts) if parts else empty


def cand_schema(channels):
    schema = {"q": pl.Int32, "p": pl.Int32}
    for ch in channels:
        schema[f"{ch['name']}_cos"] = pl.Float32
        schema[f"{ch['name']}_rank"] = pl.Int8
    return schema


def block_country(q_df: pl.DataFrame, p_df: pl.DataFrame, channels) -> pl.DataFrame:
    """Union of all channels' candidates for one country.

    q_df / p_df carry a 'gidx' column with the global row index of each record.
    Returns columns: q, p (global indices) and <ch>_cos / <ch>_rank per channel.
    """
    frames = []
    for ch in channels:
        with timer(f"  channel {ch['name']} ({q_df.height:,} x {p_df.height:,})"):
            c = _topn_channel(q_df[ch["col"]].to_list(), p_df[ch["col"]].to_list(), ch)
        frames.append(c.rename({"cos": f"{ch['name']}_cos", "rank": f"{ch['name']}_rank"}))
    schema = cand_schema(channels)
    value_cols = [c for c in schema if c not in ("q", "p")]
    # union of the channels: one row per (q, p); max() ignores the nulls of the other channels
    out = (pl.concat(frames, how="diagonal")
           .group_by(["q", "p"]).agg([pl.col(c).max() for c in value_cols])
           .with_columns([pl.col(f"{ch['name']}_cos").fill_null(0.0) for ch in channels]
                         + [pl.col(f"{ch['name']}_rank").fill_null(99) for ch in channels])
           .select(list(schema)).cast(schema))
    del frames
    qg = q_df["gidx"].to_numpy()
    pg = p_df["gidx"].to_numpy()
    return out.with_columns(
        pl.Series("q", qg[out["q"].to_numpy()], dtype=pl.Int32),
        pl.Series("p", pg[out["p"].to_numpy()], dtype=pl.Int32),
    ).sort(["q", "p"])


def block_all(q_df: pl.DataFrame, p_df: pl.DataFrame, channels=None, countries=None, out_prefix=None) -> pl.DataFrame:
    """Run blocking per country (country treated as an open set of labels); optionally only `countries`.

    With `out_prefix`, each country's candidates are written to <out_prefix>_<country>.parquet as
    soon as they are ready and the returned frame is read back from those files.
    """
    channels = channels or DEFAULT_CHANNELS
    # keep only what blocking needs so per-country filters / TF-IDF do not duplicate the whole frames
    q_df = q_df.select(["country"] + BLOCK_COLS).with_row_index("gidx").with_columns(pl.col("gidx").cast(pl.Int32))
    p_df = p_df.select(["country"] + BLOCK_COLS).with_row_index("gidx").with_columns(pl.col("gidx").cast(pl.Int32))
    parts, paths = [], []
    for country in (countries or q_df["country"].unique().sort().to_list()):
        qc = q_df.filter(pl.col("country") == country)
        pc = p_df.filter(pl.col("country") == country)
        print(f"[block] country={country!r}: {qc.height:,} queries, {pc.height:,} pool records", flush=True)
        if pc.height == 0 or qc.height == 0:
            continue
        cand = block_country(qc, pc, channels)
        del qc, pc
        if out_prefix:
            path = f"{out_prefix}_{country}.parquet"
            cand.write_parquet(path)
            paths.append(path)
            print(f"[block] {country!r}: {cand.height:,} candidates ({cand.height / max(1, (q_df['country'] == country).sum()):.1f}/query) -> {os.path.basename(path)}", flush=True)
            del cand
        else:
            parts.append(cand)
    schema = cand_schema(channels)
    if out_prefix:
        return pl.read_parquet(paths) if paths else pl.DataFrame(schema=schema)
    return pl.concat(parts) if parts else pl.DataFrame(schema=schema)

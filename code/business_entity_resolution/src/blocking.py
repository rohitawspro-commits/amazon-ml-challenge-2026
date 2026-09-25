"""Candidate generation (blocking).

Two independent retrieval channels per country, results unioned:
  * name channel    - TF-IDF over character 3-grams of the core business name
  * address channel - TF-IDF over character 3-grams of the normalised address
Each channel keeps the top-N most similar pool records (cosine) for every Source-1 query.
"""
import numpy as np
import polars as pl
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sparse_dot_topn import sp_matmul_topn

from common import N_THREADS, timer


def _topn_channel(queries, docs, top_n, thr, max_df, q_chunk=150_000, ngram=(3, 3)):
    """Top-N cosine neighbours of every query among docs. Returns (q, p, cos, rank) frame."""
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=ngram, min_df=2, max_df=max_df,
                          dtype=np.float32, sublinear_tf=True)
    P = vec.fit_transform(docs)
    PT = sparse.csr_matrix(P.T)
    del P
    parts = []
    for start in range(0, len(queries), q_chunk):
        Q = vec.transform(queries[start:start + q_chunk])
        C = sp_matmul_topn(Q, PT, top_n=top_n, threshold=thr, sort=True, n_threads=N_THREADS)
        C = sparse.csr_matrix(C)
        counts = np.diff(C.indptr)
        rows = np.repeat(np.arange(C.shape[0], dtype=np.int64), counts) + start
        rank = np.arange(len(C.indices)) - np.repeat(C.indptr[:-1], counts)
        parts.append(pl.DataFrame({
            "q": rows.astype(np.int32), "p": C.indices.astype(np.int32),
            "cos": C.data.astype(np.float32), "rank": rank.astype(np.int8),
        }))
        print(f"    queries {start + Q.shape[0]:,}/{len(queries):,}", flush=True)
    return pl.concat(parts) if parts else pl.DataFrame(
        schema={"q": pl.Int32, "p": pl.Int32, "cos": pl.Float32, "rank": pl.Int8})


def block_country(q_df: pl.DataFrame, p_df: pl.DataFrame, cfg) -> pl.DataFrame:
    """Union of name- and address-channel candidates for one country.

    q_df / p_df carry a 'gidx' column with the global row index of each record.
    Returns columns: q, p (global indices), name_cos, name_rank, addr_cos, addr_rank.
    """
    with timer(f"  name channel ({q_df.height:,} x {p_df.height:,})"):
        n = _topn_channel(q_df["core"].to_list(), p_df["core"].to_list(),
                          cfg.top_name, cfg.name_thr, cfg.max_df)
    with timer(f"  address channel ({q_df.height:,} x {p_df.height:,})"):
        a = _topn_channel(q_df["naddr"].to_list(), p_df["naddr"].to_list(),
                          cfg.top_addr, cfg.addr_thr, cfg.max_df)
    n = n.rename({"cos": "name_cos", "rank": "name_rank"})
    a = a.rename({"cos": "addr_cos", "rank": "addr_rank"})
    c = n.join(a, on=["q", "p"], how="full", coalesce=True).with_columns(
        pl.col("name_cos").fill_null(0.0), pl.col("addr_cos").fill_null(0.0),
        pl.col("name_rank").fill_null(99), pl.col("addr_rank").fill_null(99),
    )
    qg = q_df["gidx"].to_numpy()
    pg = p_df["gidx"].to_numpy()
    return c.with_columns(
        pl.Series("q", qg[c["q"].to_numpy()], dtype=pl.Int32),
        pl.Series("p", pg[c["p"].to_numpy()], dtype=pl.Int32),
    )


def block_all(q_df: pl.DataFrame, p_df: pl.DataFrame, cfg) -> pl.DataFrame:
    """Run blocking per country (country treated as an open set of labels)."""
    q_df = q_df.with_row_index("gidx").with_columns(pl.col("gidx").cast(pl.Int32))
    p_df = p_df.with_row_index("gidx").with_columns(pl.col("gidx").cast(pl.Int32))
    parts = []
    for country in q_df["country"].unique().sort().to_list():
        qc = q_df.filter(pl.col("country") == country)
        pc = p_df.filter(pl.col("country") == country)
        print(f"[block] country={country!r}: {qc.height:,} queries, {pc.height:,} pool records", flush=True)
        if pc.height == 0:
            continue
        parts.append(block_country(qc, pc, cfg))
    cand = pl.concat(parts) if parts else pl.DataFrame(
        schema={"q": pl.Int32, "p": pl.Int32, "name_cos": pl.Float32, "name_rank": pl.Int8,
                "addr_cos": pl.Float32, "addr_rank": pl.Int8})
    return cand.sort(["q", "p"])

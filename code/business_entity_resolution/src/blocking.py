"""Candidate generation (blocking).

Several independent retrieval channels per country, results unioned. A channel is a TF-IDF
vector space (word tokens or character n-grams) over one normalised text column; for every
Source-1 query it keeps the top-N most similar pool records by cosine (sparse_dot_topn).
Frequent terms are pruned with `max_df`, which is what keeps the sparse products fast.

Reverse blocking (channels with `rev_top_n` > 0): in the same TF-IDF space every pool record also
retrieves its top `rev_top_n` Source-1 entities, and those pairs join the union. A pool record
belongs to at most one entity, so its nearest entities are good candidates even when the entity's
own top-N is crowded out (chains, generic names). The reverse search always covers the whole
Source 1 of the country (training passes it apart from its query sample), so reverse ranks mean
the same at training and test time.

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

# name: short id used as feature prefix; col: normalised text column; analyzer/ngram: TF-IDF space;
# optional rev_top_n: reverse-blocking depth (Source-1 entities kept per pool record).
DEFAULT_CHANNELS = [
    {"name": "w", "col": "both", "analyzer": "word", "ngram": [1, 1], "max_df": 0.02, "top_n": 40, "thr": 0.05},
    {"name": "n3", "col": "core", "analyzer": "char_wb", "ngram": [3, 3], "max_df": 0.01, "top_n": 10, "thr": 0.10},
    {"name": "a4", "col": "naddr", "analyzer": "char_wb", "ngram": [4, 4], "max_df": 0.01, "top_n": 15, "thr": 0.10},
]
BLOCK_COLS = ["core", "naddr", "both"]


def _vectorizer(ch):
    kw = dict(analyzer=ch["analyzer"], min_df=2, max_df=ch["max_df"], dtype=np.float32, sublinear_tf=True)
    if ch["analyzer"] == "word":
        kw["token_pattern"] = r"\S+"
    else:
        kw["ngram_range"] = tuple(ch["ngram"])
    return TfidfVectorizer(**kw)


def _topn(rows, n_rows, colsT, top_n, thr, chunk):
    """Top-N cosine neighbours of every row. rows(start, end) returns that block of TF-IDF rows and
    colsT is the transposed matrix of what is retrieved. Returns a (row, col, cos, rank) frame."""
    parts = []
    for start in range(0, n_rows, chunk):
        C = sparse.csr_matrix(sp_matmul_topn(rows(start, start + chunk), colsT, top_n=top_n, threshold=thr,
                                             sort=True, n_threads=N_THREADS))
        counts = np.diff(C.indptr)
        row = np.repeat(np.arange(C.shape[0], dtype=np.int64), counts) + start
        rank = np.arange(len(C.indices)) - np.repeat(C.indptr[:-1], counts)
        parts.append(pl.DataFrame({
            "row": row.astype(np.int32), "col": C.indices.astype(np.int32),
            "cos": C.data.astype(np.float32), "rank": rank.astype(np.int8),
        }))
    empty = pl.DataFrame(schema={"row": pl.Int32, "col": pl.Int32, "cos": pl.Float32, "rank": pl.Int8})
    return pl.concat(parts) if parts else empty


def _topn_channel(queries, docs, ch, universe=None, q_chunk=150_000):
    """Forward: top-N docs (pool records) of every query, as a (q, p, cos, rank) frame of local indices.

    With `universe` (Source-1 texts) also the reverse top `rev_top_n` universe entities of every doc, as a
    (p, u, cos, rank) frame, else None. Both use the TF-IDF space fitted on the docs, so a pair found in
    both directions has the same cosine.
    """
    vec = _vectorizer(ch)
    P = vec.fit_transform(docs)
    PT = sparse.csr_matrix(P.T)
    if universe is None:
        del P
    fwd = _topn(lambda s, e: vec.transform(queries[s:e]), len(queries), PT, ch["top_n"], ch["thr"], q_chunk)
    del PT
    rev = None
    if universe is not None:
        UT = sparse.csr_matrix(vec.transform(universe).T)
        rev = _topn(lambda s, e: P[s:e], P.shape[0], UT, ch["rev_top_n"], ch["thr"], q_chunk)
        rev = rev.rename({"row": "p", "col": "u"})
        del P, UT
    return fwd.rename({"row": "q", "col": "p"}), rev


def cand_schema(channels):
    schema = {"q": pl.Int32, "p": pl.Int32}
    for ch in channels:
        schema[f"{ch['name']}_cos"] = pl.Float32
        schema[f"{ch['name']}_rank"] = pl.Int8
    for ch in channels:
        if ch.get("rev_top_n", 0):
            schema[f"{ch['name']}_rrank"] = pl.Int8
            schema[f"{ch['name']}_rbest"] = pl.Float32
    return schema


def block_country(q_df: pl.DataFrame, p_df: pl.DataFrame, channels, u_df: pl.DataFrame = None) -> pl.DataFrame:
    """Union of all channels' candidates for one country, forward and reverse.

    q_df / p_df carry a 'gidx' column with the global row index of each record. u_df is the Source-1
    universe that reverse blocking searches (default q_df); its 'gidx' is the global query index of each
    entity, null for entities that are not queries.
    Returns columns: q, p (global indices), <ch>_cos / <ch>_rank per channel (rank 99 = not in the query's
    top-N) and for reverse channels <ch>_rrank (rank of the query among the pool record's reverse
    neighbours, 99 = not among them) and <ch>_rbest (the pool record's best reverse cosine).
    """
    u_df = q_df if u_df is None else u_df
    qg, pg = q_df["gidx"].to_numpy(), p_df["gidx"].to_numpy()
    frames, best = [], []
    for ch in channels:
        n, rev = ch["name"], ch.get("rev_top_n", 0) > 0
        msg = f"  channel {n} ({q_df.height:,} x {p_df.height:,}"
        msg += f"; reverse top-{ch['rev_top_n']} of {u_df.height:,})" if rev else ")"
        with timer(msg):
            f, r = _topn_channel(q_df[ch["col"]].to_list(), p_df[ch["col"]].to_list(), ch,
                                 u_df[ch["col"]].to_list() if rev else None)
        frames.append(pl.DataFrame({"q": qg[f["q"].to_numpy()], "p": pg[f["p"].to_numpy()],
                                    f"{n}_cos": f["cos"], f"{n}_rank": f["rank"]}))
        if r is not None:
            r = r.with_columns(q=u_df["gidx"].gather(r["u"]), p=pl.Series(pg[r["p"].to_numpy()]))
            best.append(r.filter(pl.col("rank") == 0).select("p", pl.col("cos").alias(f"{n}_rbest")))
            frames.append(r.filter(pl.col("q").is_not_null())
                          .select("q", "p", pl.col("cos").alias(f"{n}_cos"), pl.col("rank").alias(f"{n}_rrank")))
        del f, r
    schema = cand_schema(channels)
    value_cols = [c for c in schema if c not in ("q", "p") and not c.endswith("_rbest")]
    # union of channels and directions: one row per (q, p); max() ignores the nulls of the other frames
    out = (pl.concat(frames, how="diagonal_relaxed")
           .group_by(["q", "p"]).agg([pl.col(c).max() for c in value_cols])
           .with_columns([pl.col(c).fill_null(0.0 if c.endswith("_cos") else 99) for c in value_cols]))
    del frames
    for b in best:  # the pool record's best reverse cosine, whichever entity it is
        out = out.join(b, on="p", how="left")
    return (out.with_columns([pl.col(c).fill_null(0.0) for c in schema if c.endswith("_rbest")])
            .select(list(schema)).cast(schema).sort(["q", "p"]))


def block_all(q_df: pl.DataFrame, p_df: pl.DataFrame, channels=None, countries=None, out_prefix=None,
              u_df: pl.DataFrame = None) -> pl.DataFrame:
    """Run blocking per country (country treated as an open set of labels); optionally only `countries`.

    With `out_prefix`, each country's candidates are written to <out_prefix>_<country>.parquet as
    soon as they are ready and the returned frame is read back from those files.
    u_df is the whole Source 1 for reverse blocking, with an Int32 column 'q' = the entity's row in q_df
    (null if it is not a query). It defaults to q_df, as at test time where every entity is a query.
    """
    channels = channels or DEFAULT_CHANNELS
    # keep only what blocking needs so per-country filters / TF-IDF do not duplicate the whole frames
    q_df = q_df.select(["country"] + BLOCK_COLS).with_row_index("gidx").with_columns(pl.col("gidx").cast(pl.Int32))
    p_df = p_df.select(["country"] + BLOCK_COLS).with_row_index("gidx").with_columns(pl.col("gidx").cast(pl.Int32))
    if u_df is not None:
        u_df = u_df.select(["country"] + BLOCK_COLS + [pl.col("q").cast(pl.Int32).alias("gidx")])
    parts, paths = [], []
    for country in (countries or q_df["country"].unique().sort().to_list()):
        qc = q_df.filter(pl.col("country") == country)
        pc = p_df.filter(pl.col("country") == country)
        uc = u_df.filter(pl.col("country") == country) if u_df is not None else None
        print(f"[block] country={country!r}: {qc.height:,} queries, {pc.height:,} pool records", flush=True)
        if pc.height == 0 or qc.height == 0:
            continue
        cand = block_country(qc, pc, channels, uc)
        del qc, pc, uc
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

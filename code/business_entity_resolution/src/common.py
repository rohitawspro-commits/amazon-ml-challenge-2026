"""Shared paths, I/O helpers and timing utilities for the entity-resolution pipeline."""
import contextlib
import os
import time

import polars as pl

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("ER_ROOT", os.path.abspath(os.path.join(_HERE, "..", "..", "..")))
DATA = os.environ.get("ER_DATA", os.path.join(ROOT, "data", "raw", "student_resource", "dataset"))
WORK = os.environ.get("ER_WORK", os.path.join(ROOT, "data", "work"))
OUT = os.environ.get("ER_OUT", os.path.join(ROOT, "output"))
MODELS = os.environ.get("ER_MODELS", os.path.join(ROOT, "models"))
N_THREADS = int(os.environ.get("ER_THREADS", os.cpu_count() or 4))

for _d in (WORK, OUT, MODELS):
    os.makedirs(_d, exist_ok=True)


def read_tsv(path: str) -> pl.DataFrame:
    """Read a challenge TSV. Files are raw tab-separated text with no quoting."""
    return pl.read_csv(
        path, separator="\t", quote_char=None, infer_schema_length=0, empty_string_is_null=False
    ).fill_null("")


def load_s1(split: str) -> pl.DataFrame:
    return read_tsv(f"{DATA}/{split}/{split}_source1.tsv")


def load_sources(split: str):
    """Return (source1, pool) where pool = source2 + source3 stacked, for 'train' or 'test'."""
    s1 = read_tsv(f"{DATA}/{split}/{split}_source1.tsv")
    pool = pl.concat([read_tsv(f"{DATA}/{split}/{split}_source{i}.tsv") for i in (2, 3)])
    return s1, pool


def load_ground_truth() -> pl.DataFrame:
    """Ground truth as one row per (source1_entity_id, matched id) pair."""
    gt = read_tsv(f"{DATA}/train/train_ground_truth.tsv")
    return (
        gt.filter(pl.col("matched_entity_ids") != "")
        .select("source1_entity_id", pl.col("matched_entity_ids").str.split(",").alias("p_id"))
        .explode("p_id")
    )


@contextlib.contextmanager
def timer(msg: str):
    t0 = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] {msg} ...", flush=True)
    yield
    print(f"[{time.strftime('%H:%M:%S')}] {msg} done in {time.time() - t0:.1f}s", flush=True)

"""Learn a native-script word -> Latin word dictionary from the training ground truth.

Many Source-2/3 names are the Source-1 name written in Devanagari / Kannada / Tamil / ... .
For every ground-truth pair whose pool name is in a native script and has the same number of
tokens as the Source-1 name, tokens are aligned positionally and co-occurrence counts collected.
The dominant Latin token for each native token is kept. Only the provided training data is used.
Output: resources/translit_map.json (used by normalize.norm_name).
"""
import json
import os
import re
from collections import Counter, defaultdict

import polars as pl

from common import load_ground_truth, load_sources
from normalize import _NONALNUM_RE, unidecode

NATIVE_RE = re.compile(r"[ऀ-෿]")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "translit_map.json")


def latin_tokens(name: str):
    s = unidecode(name).lower().replace("&", " and ")
    return _NONALNUM_RE.sub(" ", s).split()


def native_tokens(name: str):
    return [t.strip(".,()-:'\"") for t in name.split()]


def main():
    s1, pool = load_sources("train")
    gt = load_ground_truth()
    pairs = (gt.join(s1.select(pl.col("entity_id").alias("source1_entity_id"), pl.col("business_name").alias("n1")), on="source1_entity_id")
             .join(pool.select(pl.col("entity_id").alias("p_id"), pl.col("business_name").alias("n2")), on="p_id")
             .filter(pl.col("n2").str.contains(r"[ऀ-෿]")))
    print(f"native-script matched names: {pairs.height:,}")
    counts = defaultdict(Counter)
    aligned = 0
    for n1, n2 in zip(pairs["n1"].to_list(), pairs["n2"].to_list()):
        a, b = latin_tokens(n1), native_tokens(n2)
        b = [t for t in b if t]
        if len(a) != len(b):
            continue
        aligned += 1
        for la, nb in zip(a, b):
            if NATIVE_RE.search(nb):
                counts[nb][la] += 1
    print(f"aligned pairs: {aligned:,} | native tokens seen: {len(counts):,}")
    mapping = {}
    for tok, c in counts.items():
        best, n = c.most_common(1)[0]
        total = sum(c.values())
        if n >= 2 and n / total >= 0.5:
            mapping[tok] = best
    print(f"dictionary entries: {len(mapping):,}")
    # coverage on native-script pool names that were NOT matched (i.e. unseen during alignment)
    matched = set(gt["p_id"].to_list())
    unm = pool.filter(~pl.col("entity_id").is_in(list(matched)) & pl.col("business_name").str.contains(r"[ऀ-෿]"))
    tot = hit = 0
    for n in unm["business_name"].head(50_000).to_list():
        for t in native_tokens(n):
            if NATIVE_RE.search(t):
                tot += 1
                hit += t in mapping
    print(f"token coverage on unmatched native names: {hit / max(tot, 1):.3f} ({tot:,} tokens)")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(mapping, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("examples:", list(mapping.items())[:15])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

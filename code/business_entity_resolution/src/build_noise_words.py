"""Learn per-country name "noise" words from unlabelled token statistics.

Sources 2/3 decorate business names with extra words that the clean Source-1 name does not
have ("Holdings", "Uptown", "Participations", "Groupe", honorifics such as "Smt"/"Mr" ...).
For every country (in either split) we compare, over the same country's records, the document
frequency of each name token in Sources 2/3 with its frequency in Source 1. Tokens that are
at least MIN_RATIO times more frequent in Sources 2/3 (and not rare) are treated as noise and
removed from the core name. No labels are used, so the same procedure applies to countries
that only occur in the test data. Output: resources/noise_words.json.
"""
import json
import os
from collections import Counter

import polars as pl

from common import DATA
from normalize import FILLER, LEGAL, name_tokens

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "noise_words.json")
MIN_POOL_DF = 0.002
MIN_RATIO = 3.0
N_S1, N_POOL = 300_000, 400_000  # records per source file and country used for the statistics


def _scan(split, src):
    return pl.scan_csv(f"{DATA}/{split}/{split}_source{src}.tsv", separator="\t", quote_char=None,
                       infer_schema_length=0)


def _names(split, src, country, n):
    return _scan(split, src).filter(pl.col("country") == country).head(n).collect()["business_name"] \
        .fill_null("").to_list()


def _doc_freq(names):
    c = Counter()
    for n in names:
        c.update(set(name_tokens(n)[0]))
    return c


def main():
    noise = {}
    for split in ("train", "test"):
        countries = sorted(_scan(split, 1).select("country").unique().collect()["country"].drop_nulls().to_list())
        for country in countries:
            s1 = _names(split, 1, country, N_S1)
            pool = _names(split, 2, country, N_POOL) + _names(split, 3, country, N_POOL)
            a, b = _doc_freq(s1), _doc_freq(pool)
            words = []
            for t, c in b.items():
                pf, sf = c / len(pool), a.get(t, 0) / len(s1)
                if pf >= MIN_POOL_DF and pf / max(sf, 1e-5) >= MIN_RATIO and t not in LEGAL and t not in FILLER:
                    words.append(t)
            noise.setdefault(country, set()).update(words)
            print(f"{split}/{country}: {len(words)} noise words: {sorted(words)}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({k: sorted(v) for k, v in noise.items()}, open(OUT, "w", encoding="utf-8"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

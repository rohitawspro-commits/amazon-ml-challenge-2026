# Business Entity Resolution — pipeline

End-to-end pipeline that, for every Source-1 entity, finds the Source-2 / Source-3 records that
refer to the same real-world business. Everything runs on CPU; no external data or services are used.

```
data (TSV)  ->  normalise  ->  blocking (per country, name + address TF-IDF channels)
            ->  pairwise features  ->  LightGBM match probability
            ->  threshold + one-to-one assignment  ->  output/matching_results.tsv
                                                       output/candidate_pairs.tsv
```

## Layout

```
src/common.py      paths, TSV loading, timers
src/normalize.py   name/address normalisation (learned transliteration, legal-suffix stripping, abbreviations)
src/build_translit.py  learns resources/translit_map.json (native-script word -> Latin word) from train pairs
src/resources/     translit_map.json (shipped; regenerate with build_translit.py)
src/blocking.py    candidate generation: per-country top-N TF-IDF neighbours in three channels
                   (word tokens of name+address, char 3-grams of name, char 4-grams of address)
src/features.py    ~65 pairwise features (string similarity, token/number overlap, blocking scores, per-query context)
src/metrics.py     macro F0.5, decision rule (threshold + one-to-one), threshold search
src/train.py       train LightGBM on a sample of Source-1 training entities, tune threshold on validation
src/predict.py     run the pipeline on the test set and write both output files
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Data is expected under `<repo root>/data/raw/student_resource/dataset/{train,test}/` (the unzipped
`student_resource.zip`). Override with environment variables if needed:

| variable    | default                                       | meaning                              |
| ----------- | --------------------------------------------- | ------------------------------------ |
| `ER_DATA`   | `<root>/data/raw/student_resource/dataset`    | folder containing `train/` and `test/` |
| `ER_WORK`   | `<root>/data/work`                            | cache for normalised frames / candidates |
| `ER_MODELS` | `<root>/models`                               | trained model + tuned config         |
| `ER_OUT`    | `<root>/output`                               | where the two TSV outputs are written |
| `ER_THREADS`| number of CPUs                                | threads for blocking / features      |

## Reproduce

```bash
cd src

# 0) (optional — the file is shipped) relearn the transliteration dictionary from the training pairs
python3 build_translit.py

# 1) train on 200k sampled Source-1 entities, validate on 50k (≈ 45–60 min on 4 cores, ~12 GB RAM)
python3 train.py --tag v1 --n-train 200000 --n-val 50000

# 2) block + score + decide on the full test set, write output/*.tsv (≈ 1–2 h on 4 cores)
python3 predict.py --tag v1

# 3) validate the output format with the organiser's script
cd ../../../data/raw/student_resource
python3 utils/validate_submission.py \
    --matching ../../../output/matching_results.tsv \
    --candidate ../../../output/candidate_pairs.tsv \
    --test-dir dataset/test
```

`train.py` prints blocking recall, LightGBM validation log-loss, feature importance and the
macro-F0.5 threshold sweep; the chosen threshold and decision rule are stored in
`models/config_<tag>.json` and reused by `predict.py`.

## Notes

* All files are tab-separated; the loaders use `separator="\t"` and no quoting.
* `country` is treated as an open set: blocking simply groups records by the country string, and
  the per-country state-abbreviation tables fall back to "no expansion" for unseen countries
  (e.g. France in the test set).
* Model: LightGBM gradient-boosted trees (MIT licence, a few MB) — far below the 8B-parameter limit.

# Amazon ML Challenge 2026: Business Entity Resolution

**Team SJCEM**, St. John College of Engineering and Management, Palghar

Rohit Pujari · Arvind Prajapati · Shreyash Patil · Aryan Yadav

72-hour hackathon on Unstop (25–27 Sep 2026, 89,000+ registrations).
Public leaderboard: **0.959 macro F0.5** (final submission, v4).

## The problem

Business records arrive from three independent sources with no shared IDs. Names carry typos,
abbreviations, legal suffixes and transliterations; addresses are partial or reordered. Source 1 is
deduplicated. For every Source-1 business, find all Source-2 and Source-3 records that refer to the
same real-world business (zero, one or many).

- **Scale:** 1.73M Source-1 test entities against 9.97M Source-2/3 records.
- **Unseen country:** training data covers the US and India only; the test set adds **France**.
  `country` is treated as an open set, nothing is hard-coded per country.
- **Metric:** F0.5 per entity, macro-averaged. Precision counts more than recall, so a wrong merge
  costs more than a missed match.
- **Rules:** no external data or APIs; open-licence models only.

## Approach

```
TSV sources
   │
   ▼
Normalisation      transliteration map learned from training pairs, legal-suffix stripping,
   │               abbreviation expansion, house-number cleanup
   ▼
Blocking           per-country TF-IDF nearest neighbours in 3 channels:
   │               name+address words, name char 3-grams, address char 4-grams
   │               → ~53 candidates per entity, blocking recall 0.978
   ▼
Features           ~80 pairwise features: string similarity, token and number overlap,
   │               blocking scores, per-query context
   ▼
LightGBM           stage 1 trained out-of-fold on 200k sampled entities
   │               (optional stage 2 re-scores from the record's side)
   ▼
Decision           threshold tuned for F0.5 + one-to-one assignment
   │
   ▼
output/matching_results.tsv, output/candidate_pairs.tsv
```

## Results

| Version | Validation macro F0.5 | Public leaderboard |
|---|---|---|
| v2 | 0.9654 | 0.957 |
| **v4** (house-number normalisation, 4-fold stage 1) | **0.9677** (P 0.985, R 0.933) | **0.959** |

- Full test run: 91.5M candidate pairs scored, about 5 hours on a 4-core machine.
- Leaderboard probes showed France scoring about 0.91 against about 0.965 for the US and India.
  Generalising to the unseen country accounts for most of the gap between validation and leaderboard.
- Error analysis: false positives are near-identical businesses at the same address (different
  legal form, one-letter name change). False negatives are records with an empty address and only a
  fragment of the name.

## Repository layout

```
code/business_entity_resolution/
  src/common.py            paths, TSV loading, timers
  src/normalize.py         name and address normalisation
  src/build_translit.py    learns the transliteration map from training pairs
  src/build_noise_words.py learns noise words from training pairs
  src/blocking.py          candidate generation (3 TF-IDF channels, optional reverse blocking)
  src/features.py          pairwise features
  src/train.py             LightGBM training and threshold tuning
  src/stage2.py            record-side second stage
  src/predict.py           full test-set run, writes both output files
  src/metrics.py           macro F0.5 and decision rule
  src/error_analysis.py    false positive / false negative report
  README.md                detailed run instructions
models/                    trained LightGBM models and tuned configs (v1, v2, v4)
submissions/               zipped leaderboard submissions
Documentation_template.md  methodology write-up
```

## Run it

The dataset is not included in this repository. Place the organisers' `student_resource/` folder
under `data/raw/`.

```bash
pip install -r code/business_entity_resolution/requirements.txt
cd code/business_entity_resolution/src
python3 train.py --tag v4 --n-train 200000 --n-val 50000 --folds 4 --lr 0.08   # ~2 h, ~12 GB RAM
python3 predict.py --tag v4                                                     # ~5 h on 4 cores
```

See [`code/business_entity_resolution/README.md`](code/business_entity_resolution/README.md) for all
options and environment variables.

## Tech stack

Python · Polars · scikit-learn (TF-IDF) · LightGBM · RapidFuzz · Kaggle notebooks

# Amazon ML Challenge 2026 — Business Entity Resolution (team SJCM)

Team SJCM: Rohit, Shreyash Patil, Aryan, Arvind Prajapati. Talk to the user in Hinglish (Roman Hindi).

**Deadline: 27 Sep 2026, 11:59 PM IST** (Unstop, 72-hour hackathon). Results for the top 50 teams on 2 Oct.

## Task (from the problem statement PDF)

- Three sources of business records (`entity_id`, `business_name`, `business_address`, `country`).
  Source 1 is deduplicated. For every Source-1 entity, find all matching Source-2/3 records (0, 1 or many).
- Train: US + India with ground truth. Test: US + India + **France** (unseen). Treat `country` as an open set, never hard-code.
- Metric: F0.5 per Source-1 entity, macro-averaged. Singletons count: an empty prediction scores 1.0, any match scores 0.
  Public leaderboard is a subset of test, final ranking uses the private remainder, so do not overfit the public score.
- Outputs (tab-separated, one row per test S1 entity, no duplicates, S2/S3 IDs only):
  `output/matching_results.tsv` (scored, uploaded to the portal) and `output/candidate_pairs.tsv`
  (the exact candidate set the model scored; matches must be a subset).
- Rules: no external data, APIs or lookups (disqualification). Model licence MIT/Apache 2.0, at most 8B parameters.
- Final zip `SJCM_submission.zip`: `output/` (both TSVs), `code/business_entity_resolution/` (src, README, requirements),
  and the filled-in `Documentation_template.md`. Top teams' packages are reproduced and audited.

## Data

Google Drive folder: https://drive.google.com/drive/folders/1bcJiltepYMEGJ_A54fFM4u_LQmPbzjBt

```bash
pip install gdown -r code/business_entity_resolution/requirements.txt
gdown --folder "https://drive.google.com/drive/folders/1bcJiltepYMEGJ_A54fFM4u_LQmPbzjBt" -O data/raw/gdrive
cd data/raw && unzip -q gdrive/*_student_resource.zip   # -> data/raw/student_resource/{dataset,utils}
```

Test: 1,732,545 S1 entities, 9,969,589 S2+S3 records. `data/`, `output/*.tsv` and `*.zip` are git-ignored,
so keep copies of outputs outside the container.

## Pipeline

See `code/business_entity_resolution/README.md` and `Documentation_template.md` for details.
normalise -> per-country TF-IDF blocking (3 channels) -> ~65 pairwise features -> LightGBM -> threshold + one-to-one.

```bash
cd code/business_entity_resolution/src
python3 train.py --tag v2 --n-train 200000 --n-val 50000   # ~12 GB RAM, 45-60 min on 4 cores
python3 predict.py --tag v2                                # writes output/*.tsv
cd ../../../data/raw/student_resource && python3 utils/validate_submission.py \
  --matching ../../../output/matching_results.tsv --candidate ../../../output/candidate_pairs.tsv --test-dir dataset/test
./package.sh SJCM                                          # from repo root -> SJCM_submission.zip
```

## Status

Working branch: `claude/quirky-cray-iffodx` (merged from `claude/rohit-intro-lwmrmr`).
The repo default branch `arvind/ml-pipeline` holds only an empty skeleton.

Leaderboard on 26 Sep, 11:55 AM IST: 1st 0.9906, 6th 0.988, 50th 0.985 (only the top 50 reach the results).
Our v2 validation is 0.965, so we need at least +2 points, and the cutoff will rise before the deadline.

- [x] Pipeline code
- [x] Models: v1 val macro-F0.5 0.9660, v2 0.9654 (v2 is current; precision 0.984, recall 0.927, blocking recall 0.977)
- [ ] Test predictions with v2 (started 26 Sep 00:38 UTC; ~7 h on 4 cores: blocking ~3 h, features + scoring ~4 h)
- [ ] Validate and upload `matching_results.tsv` to the portal (gives the real test score)
- [ ] Improvements, big levers first. Recall is lost at the model stage (~5% of true pairs) more than at blocking (2.3%).
  1. Reverse blocking: for every S2/S3 record, find its top-5 S1 entities (each record belongs to at most one S1)
     and union them with the forward candidates. Add mutual-best-match features (is this S1 the record's best S1?).
  2. Cross-source consensus: link S2/S3 copies of the same business to each other (3.46 copies per S1 on average),
     then use them together, e.g. a second-stage model with "similarity to this entity's most confident match".
  3. Better transliteration of native-script words (the learned dictionary covers 92% of native tokens).
  4. Faster runs: cache features, reuse candidates (`--cand-tag`), a bigger machine if the team has AWS credits.
  5. Smaller gains: per-entity expected-F0.5 decision, per-entity sample weights, more training data, ensemble.
  For every change, pick the validation cutoff that keeps precision >= 0.984, and keep the change only if
  recall and macro F0.5 both rise.
- [ ] Documentation TBDs: test candidate-pair counts, false positive/negative examples, appendix (team name: SJCM)
- [ ] `./package.sh SJCM`

Update this section and push after every step.

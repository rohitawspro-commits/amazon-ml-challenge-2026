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

- [x] Pipeline code
- [x] Models: v1 val macro-F0.5 0.9660, v2 0.9654 (v2 is current; precision 0.984, recall 0.927, blocking recall 0.977)
- [ ] Test predictions with v2 (started 26 Sep 00:38 UTC, log in `data/predict_v2.log`)
- [ ] Validate and upload `matching_results.tsv` to the portal
- [ ] Improvements, in order: blocking recall towards 0.99; per-entity expected-F0.5 decision instead of one threshold;
      second-stage model with cross-candidate features (S2<->S3 agreement); more training data and a model ensemble
- [ ] Documentation TBDs: team name, test candidate-pair counts, false positive/negative examples, appendix
- [ ] `./package.sh SJCM`

Update this section and push after every step.

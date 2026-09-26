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
- Organisers' update on the problem page (26 Sep): `candidate_pairs.tsv` now counts toward the final ranking. Blocking
  has to scale, and an approach with a smaller candidate set ranks higher in the final evaluation, beyond the
  leaderboard score (read the full text on the Unstop problem page).

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
normalise -> per-country TF-IDF blocking (3 channels, forward + reverse) -> ~80 pairwise and record-side features
-> stage-1 LightGBM (out-of-fold) -> stage-2 LightGBM from the record's side -> threshold (precision floor) + one-to-one.

```bash
cd code/business_entity_resolution/src
python3 train.py --tag v2 --n-train 200000 --n-val 50000   # ~12 GB RAM, 45-60 min on 4 cores (forward blocking, stage 1 only)
python3 train.py --tag v4rev --rev-top-n 5 --rev-depth 2 --folds 4 --lr 0.08   # + reverse blocking, margins, stage 2; ~6-7 h
python3 predict.py --tag v2                                # writes output/*.tsv
cd ../../../data/raw/student_resource && python3 utils/validate_submission.py \
  --matching ../../../output/matching_results.tsv --candidate ../../../output/candidate_pairs.tsv --test-dir dataset/test
./package.sh SJCM                                          # from repo root -> SJCM_submission.zip
```

## Status

Working branch: `claude/quirky-cray-iffodx` (merged from `claude/rohit-intro-lwmrmr`).
The repo default branch `arvind/ml-pipeline` holds only an empty skeleton.

Leaderboard on 26 Sep, 11:55 AM IST: 1st 0.9906, 6th 0.988, 50th 0.985 (only the top 50 reach the results).
Our v2 scores 0.957 on the public leaderboard (validation 0.965), so we need about +3 points, and the cutoff will
rise before the deadline.

- [x] Pipeline code
- [x] Models: v1 val macro-F0.5 0.9660, v2 0.9654 (v2 is current; precision 0.984, recall 0.927, blocking recall 0.977)
- [x] Test predictions with v2: 6 h 41 min on 4 cores (blocking 2 h 50 min, features + scoring 3 h 45 min),
      91.55M candidate pairs (52.8 per entity). Matches per entity: France 3.17, India 3.20, US 3.27; predicted
      singletons 5.7-6.2%, so France behaves like the training countries. Both outputs pass
      `validate_submission.py --check-ids`.
- [x] v2 uploaded on 26 Sep, 1:22 PM IST: public leaderboard 0.957. The zipped `matching_results.tsv` is in
      `submissions/v2/matching_results.zip` (the TSV is 90 MB and the chat can only send files up to 30 MiB).
- The first v2 run was killed (out of memory) while writing `candidate_pairs.tsv`. `predict.py` now frees memory and
  writes the lists in chunks, and `--from-scores` rebuilds both outputs from `data/work/test_scored_<tag>.parquet`
  in under a minute.
- [ ] Improvements, big levers first. Recall is lost at the model stage (~5% of true pairs) more than at blocking (2.3%).
  1. Reverse blocking: for every S2/S3 record, find its top-5 S1 entities (each record belongs to at most one S1)
     and union them with the forward candidates. Add mutual-best-match features (is this S1 the record's best S1?).
     Core idea: decide from the record's side. True copies are very similar to their own S1, so for each record
     the useful signals are its best S1 and the margin to the second-best S1 (reverse cosine gap), and after the
     first LightGBM pass a second stage per record: its best and second-best probability, their gap, and whether
     this S1 is its top choice. Train the second stage on out-of-fold first-stage scores. Report reverse top-1
     recall: it says how often a record's best S1 is its true S1.
     Done (26 Sep, Rohit's chat): `--rev-top-n N` runs the reverse search in every channel over the whole Source 1;
     candidates carry `<ch>_rrank` (this S1's rank among the record's nearest S1s), `<ch>_rbest` / `_r2nd` (the record's
     best and second-best reverse cosine). Margin features `<ch>_rtop`, `_rgap` (= rbest - r2nd), `_rdiff` (= cos - rbest),
     `n_rtop`, `min_rrank`. `--rev-depth K` keeps reverse-only pairs up to rank K (default auto = smallest depth within
     0.0005 recall of the full depth). `stage2.py` + `--folds F`: stage 1 is trained out-of-fold over the training
     queries, stage 2 re-scores each pair with the record's best / second-best stage-1 probability, the margin over the
     record's strongest other S1, whether this S1 is its top choice, the same from the entity's side, plus the reverse
     margins. Thresholds are picked with `--min-prec 0.984`; `--reuse-cand/--reuse-feats/--reuse-stage1` resume a run.
     India blocking recall, 50k validation split, v3 normalisation (forward = 0.9617 at 52.8 cand/query):
     +reverse top-1 0.9671 (56.1), top-2 0.9695 (62.8), top-3 0.9709 (72.1), top-5 0.9729 (89.8). Reverse top-1 alone
     finds the true S1 for 92.0% of true pairs with 8.8 cand/query (word channel alone 90.2% at 4.6; n3 27.6%, a4 71.2%),
     so a record's nearest entity is usually the right one. Depth 2 chosen: most of the gain for +10 candidates/entity.
     Caveat: the sample holds 11% of Source 1, so a record's competing S1s are thinner in training than at test time,
     where every S1 is a query. The reverse-cosine margins are computed over the whole Source 1 and are test-consistent;
     the stage-2 probability margins are not, so a stage-2 gain on validation may shrink on the test set.
     Full blocking report, v4 normalisation, 50k validation split (US + India; `models/blocking_v4rev.json`):
     forward 0.9776 at 53.1 cand/query; +reverse top-1 0.9822 (55.9), top-2 0.9837 (62.5), top-3 0.9846 (71.2),
     top-5 0.9856 (90.1). Reverse alone: top-1 0.9502 at 8.6 cand/query, top-2 0.9622 at 19.8, top-3 0.9675 at 31.7,
     i.e. a record's nearest S1 is the true one for 95% of true pairs. With depth 2 the candidate set is 62.8/entity
     at recall 0.9838 (v2: 53.1 at 0.9767). A reverse-only shortlist (top-2/3) would be 2-3x smaller than forward
     blocking for 1-2 points of blocking recall: an option if the candidate count matters more in the final ranking.
     Blocking took 4.6 h on 4 cores (the reverse pass is as large as forward blocking over all of Source 1), features
     3.5 min. The first run died out of memory (exit 137) when LightGBM binned 12.6M x 95 features next to the raw
     matrix; train.py now frees the raw matrix after binning and reloads each held-out fold, and reuses the cached
     candidates and features: `train.py --tag v4rev --rev-top-n 5 --rev-depth 2 --folds 4 --lr 0.08 --reuse-cand
     --reuse-feats` (restarted 26 Sep ~14:50 UTC, ~2 h; log in the container only). It prints the full blocking report (US + India, reverse
     top-1 recall), stage 1 and stage 2 validation at precision >= 0.984 with per-country numbers, and the v2 comparison;
     the results land in `models/config_v4rev.json` and `models/blocking_v4rev.json`. `predict.py --tag v4rev` runs
     both stages on the test set (reverse blocking roughly doubles test blocking time).
- Leaderboard probes (26 Sep): `submissions/probes/matching_results_noFR.zip` and `_noIN.zip` are v2 with every
  France (or India) row left empty; both pass the validator. Test shares: France 0.150, India 0.4675, US 0.3827;
  predicted empty rates: France 0.057, India 0.062, US 0.059. With LB scores v2 = 0.957, noFR and noIN:
  Probe results (26 Sep, 2:50 PM IST): noFR = 0.829, noIN = 0.573. With India and US at their validation level
  (0.965) the numbers fit exactly: France ~ 0.91, and the public subset is about France 0.15, India 0.42, US 0.43.
  So France alone explains the whole validation-to-leaderboard gap. A perfect France would give ~0.970 overall,
  so 0.98 also needs India + US at ~0.985.
- France diagnosis (20k-entity sample per country, v2 test candidates and scores). Per S1 entity France has 0.83
  exact-looking candidates (same core name, street and house number; India 0.42, US 0.60), 0.54 same-name and
  same-street candidates with a different house number (India 0.15, US 0.62; v2 accepts 19% of them in France
  against 30-49% elsewhere) and 1.05 same-address candidates with a different name (India 0.40, US 0.62; accepted
  33% against 50-71%), plus 30-50% more unsure pairs. The record-side second stage is the right tool for this:
  give a record to the S1 it clearly prefers, drop a record split between two S1s.
- Normalisation v4 (26 Sep): zero-padded house numbers ("0029" vs "29") were different number tokens. 3.0% of all
  true training pairs have one (US 4.0%, India 1.5%; 2.9% of France test records), and after stripping the zeros
  87% of them get an equal first number. Every model must be retrained on v4 features; v2 stays the uploaded
  baseline and must not be re-run with the new normalisation.
- Same-name pairs whose S2/S3 address is empty score 0.66-0.67, just under the 0.70 cutoff ("Pornic Danse SARL",
  "ZV Élémentaire SAS"); 3.3% of records have empty addresses. Check that bucket on validation.
  2. Error analysis before any new feature: on validation, split missed matches into "not in the shortlist",
     "in the shortlist but below the cutoff" and "removed by one-to-one", and wrong matches into "same name,
     different address", "same address, different business" and "other", with ~20 examples each; build features
     for the biggest bucket. Cross-source consensus was checked and dropped: on 30k training entities (110,588 true
     copies), only 2.2% of copies have name+address token-set similarity < 70 to their S1, and for the hardest
     0.8% the other copies are no closer than the S1 record (median 58 vs 57), so it could rescue about 1-2% of them.
  3. Transliteration is low priority: among the hardest copies (similarity to S1 < 60) only 1.9% have non-Latin
     names, against 13.7% of all copies, so the learned dictionary already handles scripts well.
  Team split (details and commands in `TEAM_SETUP.md`): Shreyash runs the error analysis on Kaggle, Aryan builds the
  pruning stage on Kaggle, Arvind runs the 500k-entity training run and the final test run on AWS, and Rohit's chat
  does reverse blocking plus mutual-best features and merges everyone's branches.
  Hybrid (target 0.98+): add a small cross-encoder that re-scores only the pairs LightGBM is unsure about.
  - Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (Apache-2.0, 22M parameters) fine-tuned as a binary matcher with
    sentence-transformers `CrossEncoder`. Input per side: "name: <core> | address: <naddr>" (normalised fields, so
    native scripts are already transliterated), max_length 96, 1-2 epochs, lr 2e-5.
  - Training pairs: labelled candidates from a `train.py` run (positives = ground truth), mostly pairs with LightGBM
    probability between 0.02 and 0.98, plus a sample of confident ones.
  - Blend on validation: p = (1 - w) * p_lgb + w * p_ce for the unsure pairs. Choose w and the cutoff with precision
    >= 0.984, and keep the blend only if macro F0.5 rises.
  - Compute: Shreyash fine-tunes on a Kaggle GPU after the error analysis; Arvind scores the unsure test pairs on the
    32-core AWS machine (a few million short pairs is feasible on CPU). Save the weights in fp16 (~45 MB) so they
    fit on GitHub.
  4. Faster runs: cache features, reuse candidates (`--cand-tag`), a bigger machine if the team has AWS credits.
  5. Smaller gains: per-entity expected-F0.5 decision, per-entity sample weights, more training data, ensemble.
  For every change, pick the validation cutoff that keeps precision >= 0.984, and keep the change only if
  recall and macro F0.5 both rise.
  Report candidates per entity next to recall for every change (v2: 52.8), since the candidate set size now counts in
  the final ranking. Reverse blocking adds candidates, so keep its depth small, and add a cheap pruning stage (e.g. a
  small model on the blocking scores) before the full features so the final candidate set shrinks. Fewer candidates
  also cut the ~4 h feature time.
- [ ] Documentation: only the false positive/negative examples are left (they need validation predictions). Team name,
      test candidate counts and the test-run statistics are filled in for v2; update them if the final model changes.
- [ ] `./package.sh SJCM` with the final outputs. `candidate_pairs.tsv` is 1.2 GB, so the zip is far above the 30 MiB
      chat limit and GitHub's 100 MB file limit. Send it to the user in parts under 30 MiB (`split -b 29m`) and have
      them join the parts with `cat SJCM_submission.zip.part-* > SJCM_submission.zip`.

Update this section and push after every step.

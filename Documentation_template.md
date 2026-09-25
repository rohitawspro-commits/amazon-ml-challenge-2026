# ML Challenge 2026: Business Entity Resolution Solution Template

**Team Name:** [TEAM NAME]
**Team Members:** Rohit, Shreyash Patil, Aryan, Arvind Prajapati
**Submission Date:** 26 September 2026

---

## 1. Executive Summary

We treat the task as *retrieve-then-classify* entity resolution. For every Source-1 entity we
retrieve a small candidate set from Source 2 + Source 3 with two complementary character-n-gram
TF-IDF channels (business name and address), score every (Source-1, candidate) pair with a
LightGBM classifier over ~60 string-similarity and context features, and turn the scores into
matches with a precision-oriented threshold tuned for macro F0.5 plus a one-to-one assignment
constraint that exploits the fact that Source 1 is deduplicated. The pipeline is CPU-only,
uses no external data, and is country-agnostic (France, unseen in training, is handled by the
same code path).

---

## 2. Methodology

### 2.1 Problem Analysis

Key facts we measured on the training data (2.2M Source-1 entities, 10.3M Source-2/3 records):

* Every Source-1 entity has on average **3.46** matching records (max 11); only **5.6 %** are
  singletons. Recall therefore matters even though F0.5 is precision-weighted.
* **74 %** of Source-2/3 records belong to some Source-1 entity; the remaining 26 % are
  distractors. These distractors are *other businesses* (only 0.4 % of them share an exact
  normalised address with any Source-1 record), not near-duplicates of Source-1 entities.
* No Source-2/3 record is matched to more than one Source-1 entity, and matched pairs always share
  the same `country` label. Both facts are used directly (one-to-one assignment; blocking per
  country).
* Name noise: legal-suffix variants (`Pvt Ltd` / `Private Limited` / `प्रा. लि.`), suffix moved to the
  front (`LLC Curley Lifec0`), stutter duplicates (`Peridance Peridance`), filler words
  (`Service`, `Center`, `The`, `Sri`), DBA / "formerly:" prefixes, junk symbols (`>>`, `--`, `##`),
  accented characters (`Télecom`), digit/letter substitutions (`Nati0nal`, `5pecialists`),
  keyboard typos (`Cotllere`, `Ggmrowth`), truncation (`Brown, Dixon &`), word-order changes, and
  the name rewritten as a domain (`hrsinvestments.com`, `mediashivaprivate.com`).
* **15 % of Source-2 and 11 % of Source-3 names are written in a non-Latin script**
  (Devanagari, Kannada, Tamil, Bengali, … transliterations of the English name), and ~9 % of
  addresses contain native-script state names.
* Address noise: abbreviations (`Rd`/`Road`, `Ct`/`Court`), state as abbreviation / full name /
  native script, component re-ordering (`CA, 6854 Aleta Way, Sacramento`), dropped components,
  misspelt cities (`SACCRAMENTO`), city replaced by township/county/CDP, altered house numbers
  (`6854` -> `685`), and 3.3 % empty addresses.

### 2.2 Solution Strategy

**Approach Type:** Blocking + pairwise classifier (retrieve-then-classify), with a global
one-to-one post-processing step.
**Core Innovation:** two independent retrieval channels (name *and* address) so that a record whose
name is destroyed (domain, native script, truncation) is still recovered through its address, and
vice-versa; plus per-query *context* features (how a candidate compares with the other candidates
of the same Source-1 entity) that let the classifier make relative decisions.

---

## 3. Candidate Generation (Blocking)

* **Blocking keys used:**
  1. `country` (exact; treated as an open set of strings).
  2. Name channel: TF-IDF over character 3-grams (`char_wb`, sublinear tf, `min_df=2`,
     `max_df=0.05`) of the *core* name — lower-cased, transliterated with `unidecode`, `&`->`and`,
     dotted abbreviations collapsed (`L.L.C.` -> `llc`), domain names reduced to their label,
     legal-form and filler tokens removed, stutter duplicates removed, `0`->`o` / `5`->`s` inside
     words. Top-20 cosine neighbours per query (`sparse_dot_topn`).
  3. Address channel: TF-IDF over character 3-grams of the normalised address — transliterated,
     native-script state names mapped to English, per-country state abbreviations expanded
     (`NC` -> `north carolina`, `KA` -> `karnataka`; unseen countries skip this), street
     abbreviations expanded (`st` -> `street`, `rd` -> `road`, …). Top-20 cosine neighbours per
     query.
  The two channels are unioned; each channel's cosine score and rank are kept as features.
* **Candidate pairs generated:** TBD_CAND_PAIRS on the test set (TBD_CAND_PER_Q per Source-1 entity;
  reduction ratio ≈ 1 − TBD_CAND_PER_Q / 10M).
* **How you ensured true matches were not lost:** blocking recall is measured on a 250k-entity
  training sample against the *full* training pool: TBD_RECALL overall (name channel alone
  TBD_RECALL_NAME, address channel alone TBD_RECALL_ADDR). The union of two channels is what keeps
  recall high: names in native script or written as a domain are recovered by the address channel,
  and records with an empty / shortened address are recovered by the name channel.

---

## 4. Matching Model

**Features used** (all computed per (Source-1, candidate) pair):

* Name features: `rapidfuzz` ratio, token-sort ratio, token-set ratio and partial ratio on the
  full normalised name; ratio, token-set ratio and Jaro–Winkler on the core name; ratio and partial
  ratio on the space-less core name (robust to domain-style concatenation); TF-IDF cosine and rank
  from the name channel; core-token Jaccard / intersection / coverage in both directions; first-token
  equality; lengths and token counts of both sides.
* Address features: ratio, token-sort, token-set and partial ratio on the normalised address;
  TF-IDF cosine and rank from the address channel; address-token Jaccard; numeric-token Jaccard and
  intersection (house numbers, PIN codes); first-number (house number) equality; number counts;
  empty-address flag.
* Other: whether the candidate was retrieved by both channels; candidate name is a domain;
  candidate name was non-Latin; **per-query context**: for eight key scores the maximum over all
  candidates of the same Source-1 entity and the gap between this candidate and that maximum,
  the number of candidates, and the candidate's rank by a combined score.

**Model type:** LightGBM binary classifier (gradient-boosted trees, MIT licence; 127 leaves,
learning-rate 0.05, early-stopped on validation log-loss). Trained on TBD_TRAIN_PAIRS candidate
pairs from 200k randomly sampled Source-1 training entities blocked against the full 10.3M-record
training pool (positives = pairs present in the ground truth).

**Threshold selection method:** grid search of the probability threshold (0.20–0.95, step 0.02) on a
held-out validation split of 50k Source-1 entities, maximising **macro F0.5 computed exactly as the
leaderboard does** (singletons included). Two decision rules were compared: plain thresholding and
threshold + one-to-one assignment (each Source-2/3 record is given only to the Source-1 entity with
the highest probability). Selected: TBD_RULE at threshold TBD_THR.

---

## 5. Results & Error Analysis

* **F_0.5 Score (macro):** TBD_F05 on the 50k-entity validation split (macro precision TBD_P,
  macro recall TBD_R, singleton accuracy TBD_SING).
* **Common false positives (wrong merges):** TBD_FP
* **Common false negatives (missed matches):** TBD_FN

---

## 6. Conclusion

A carefully normalised, two-channel TF-IDF blocking stage combined with a feature-rich gradient
boosting matcher and a precision-tuned, one-to-one decision rule gives a strong, fully reproducible
CPU-only solution. The biggest lessons: (1) address retrieval is essential because a large share of
name fields are transliterated, truncated or rewritten as domains; (2) context features and the
one-to-one constraint are what convert good pairwise scores into high per-entity precision.

---

## Appendix

### A. Code Artefacts

`code/business_entity_resolution/` — `src/normalize.py` (normalisation), `src/blocking.py`
(candidate generation), `src/features.py` (pairwise features), `src/metrics.py` (macro F0.5,
decision rule, threshold search), `src/train.py` (training + threshold tuning) and
`src/predict.py` (test inference, writes `output/matching_results.tsv` and
`output/candidate_pairs.tsv`). `README.md` in that folder gives the exact commands;
`requirements.txt` pins every dependency.

### B. Additional Results

TBD_EXTRA

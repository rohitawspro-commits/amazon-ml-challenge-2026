# ML Challenge 2026: Business Entity Resolution Solution Template

**Team Name:** SJCM
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

* **Normalisation first.** Names: lower-cased, native-script words mapped through a
  *learned* dictionary (see below) and the rest transliterated with `unidecode`, `&`->`and`,
  dotted abbreviations collapsed (`L.L.C.` -> `llc`), domain names reduced to their label,
  legal-form and filler tokens removed to obtain a *core* name, stutter duplicates removed,
  `0`->`o` / `5`->`s` inside words. Addresses: transliterated, native-script state names mapped to
  English, per-country state abbreviations expanded (`NC` -> `north carolina`,
  `KA` -> `karnataka`; unseen countries such as France simply skip this table), street
  abbreviations expanded (`st` -> `street`, `rd` -> `road`, …), numeric tokens extracted.
* **Learned noise words.** Sources 2/3 decorate names with extra words that Source 1 does not
  carry (`Holdings`, `Uptown`, `Overseas`, `Participations`, `Groupe`, honorifics `Mr`/`Smt` …).
  For every country we compare, without any labels, the document frequency of each name token
  in Sources 2/3 with its frequency in Source 1; tokens at least 3× more frequent in Sources 2/3
  are removed from the core name. Because no labels are needed, the same statistic is computed
  for France from the test files (18 US, 7 Indian and 8 French words in total).
* **French address forms.** Source 1 writes `17 Rue du Commandant`, Sources 2/3 write
  `NO 17 R DU COMMANDANT` / `N° 17 R. …`: number markers (`No`, `N°`) are dropped, `R`/`Q`/`Imp`/`All`/`Ch`/`Crs`
  are expanded, and departments are mapped to their region (`Nord` -> `Hauts-de-France`,
  `Gironde` -> `Nouvelle-Aquitaine`) because the two sources use different levels.
* **Learned transliteration dictionary.** 15 % of Source-2 and 11 % of Source-3 names are the
  English name written in Devanagari / Kannada / Tamil / Bengali / Gujarati / Telugu … . From the
  551k ground-truth pairs whose pool name is in a native script we align tokens positionally with
  the Source-1 name and keep the dominant Latin word for each native word. The vocabulary is small
  (1,347 native tokens) and the dictionary covers 92 % of native tokens in *unmatched* names
  (`श्याम कंसल्टिंग प्रा. लि.` -> `shyam consulting pvt ltd`). Only the provided training data is
  used.
* **Blocking keys used:**
  1. `country` (exact; treated as an open set of strings).
  2. **Word channel** (main): TF-IDF over word tokens of `core name + normalised address`
     (`min_df=2`, `max_df=0.02`, sublinear tf); top-40 cosine neighbours per query
     (`sparse_dot_topn`). Name and address evidence are combined in one vector space, so a
     record whose name is garbled is still retrieved by its address and vice-versa, and common
     names are disambiguated by address words.
  3. **Name char channel**: TF-IDF over character 3-grams of the core name (`max_df=0.01`),
     top-10 — robust to typos inside words.
  4. **Address char channel**: TF-IDF over character 4-grams of the normalised address
     (`max_df=0.01`), top-15.
  The channels are unioned; each channel's cosine score and rank are kept as features. Pruning
  frequent terms with `max_df` is what makes the sparse products tractable (the word channel
  processes 20k queries against 4.1M Indian records in ~36 s on 4 cores).
* **Candidate pairs generated:** 91,553,641 on the test set, i.e. 52.8 per Source-1 entity across 1,732,544 entities
  (5 entities get no candidate). Against all 1.73M × 9.97M Source-1 × Source-2/3 pairs the reduction ratio is
  1 − 91.6M / 1.73e13 ≈ 0.999995.
* **How you ensured true matches were not lost:** blocking recall is measured on a 250k-entity
  training sample against the *full* 10.3M-record training pool: **0.977** pair recall overall
  (word channel alone 0.972, name char channel 0.424, address char channel 0.813), with 53
  candidates per Source-1 entity on average. On a 20k-query Indian development sample (before the transliteration
  dictionary) the word channel alone reached 0.919 pair recall at top-25 and the three-channel
  union 0.931; a single character-3-gram name channel, the textbook choice, reached only 0.52
  because common business names collide massively in a 4M-record pool.

---

## 4. Matching Model

**Features used** (all computed per (Source-1, candidate) pair):

* Name features: `rapidfuzz` ratio, token-sort ratio, token-set ratio and partial ratio on the
  full normalised name; ratio, token-set ratio and Jaro–Winkler on the core name; ratio and partial
  ratio on the space-less core name (robust to domain-style concatenation); core-token Jaccard /
  intersection / coverage in both directions; first-token equality; lengths and token counts of
  both sides.
* Address features: ratio, token-sort, token-set and partial ratio on the normalised address;
  address-token Jaccard; numeric-token Jaccard and intersection (house numbers, PIN codes);
  first-number (house number) equality; number counts; empty-address flag.
* Blocking features: cosine score and rank in each of the three channels, number of channels that
  retrieved the candidate; IDF-weighted word cosines of the core names and of the addresses
  (word TF-IDF spaces fitted on the pool), which down-weight ubiquitous words such as city names.
* Other: candidate name is a domain; candidate name was non-Latin; **per-query context**: for nine
  key scores the maximum over all candidates of the same Source-1 entity and the gap between this
  candidate and that maximum, the number of candidates, and the candidate's rank by a combined
  score.

**Model type:** LightGBM binary classifier (gradient-boosted trees, MIT licence; 127 leaves,
learning-rate 0.05, up to 3,000 rounds, early-stopped on validation log-loss; ~37 MB model file). Trained on 10.6M candidate
pairs from 200k randomly sampled Source-1 training entities blocked against the full 10.3M-record
training pool (positives = pairs present in the ground truth).

**Threshold selection method:** grid search of the probability threshold (0.20–0.95, step 0.02) on a
held-out validation split of 50k Source-1 entities, maximising **macro F0.5 computed exactly as the
leaderboard does** (singletons included). Two decision rules were compared: plain thresholding and
threshold + one-to-one assignment (each Source-2/3 record is given only to the Source-1 entity with
the highest probability). Selected: threshold **0.70** with one-to-one assignment (the sweep is flat between 0.62 and 0.78).

---

## 5. Results & Error Analysis

* **F_0.5 Score (macro):** **0.9654** on the 50k-entity validation split (macro precision 0.984,
  macro recall 0.927, singleton accuracy 0.954; pair-level precision 0.989, pair-level recall 0.927).
  LightGBM validation log-loss 0.0101 (learning-rate 0.05, 127 leaves, early stopping on the
  validation split). An earlier variant without the learned noise words and IDF-weighted cosines
  scored 0.9660 — i.e. the two are within noise of each other; the final model keeps the extra
  features because they make the pipeline more robust on the unseen French records.
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

Test-set run of the final model (v2) on 4 CPU cores and 15 GB RAM: normalisation 2.4 min, blocking about 2 h 50 min,
features + scoring 3 h 45 min (6 h 41 min in total). Predicted matches per Source-1 entity and predicted singleton rate:

| Country | Source-1 entities | Matches per entity | Predicted singletons |
| ------- | ----------------: | -----------------: | -------------------: |
| France  |           259,452 |               3.17 |                 5.7% |
| India   |           809,986 |               3.20 |                 6.2% |
| US      |           663,106 |               3.27 |                 5.9% |

France has no training data, yet it gets about the same match rate as the two training countries (the training ground
truth has 3.46 matches per entity and 5.6% singletons), which suggests the pipeline carries over to the unseen country.

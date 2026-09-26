# Amazon ML Challenge 2026 — Business Entity Resolution

Team: Rohit, Shreyash Patil, Aryan, Arvind Prajapati

Task: for every Source-1 business, find its records in Source 2 and Source 3 (noisy names /
addresses, three countries). Scored by macro F0.5 — false merges cost more than missed matches.

## Repo layout (mirrors the required submission package)

```
code/business_entity_resolution/   pipeline (src/), README.md with run instructions, requirements.txt
output/                            matching_results.tsv + candidate_pairs.tsv (generated, not committed)
Documentation_template.md          methodology write-up
data/                              raw dataset + caches (git-ignored — download separately)
```

## Quick start

```bash
pip install -r code/business_entity_resolution/requirements.txt
# put the unzipped student_resource/ folder under data/raw/
cd code/business_entity_resolution/src
python3 train.py --tag v1          # train + tune threshold (prints validation macro F0.5)
python3 predict.py --tag v1        # writes output/*.tsv for the test set
```

See `code/business_entity_resolution/README.md` for details.

# Team SJCM: Kaggle aur AWS pe kaam kaise karein

Deadline: **27 Sep, 11:59 PM IST**. Poora context `CLAUDE.md` mein hai.

## 1. Sabse pehle (Rohit, abhi)

1. **Repo private hai** (26 Sep ko confirm kiya). Ise public mat karna, isme hamara code, models aur test output hai.
2. **Access:** Aryan (`aryan7841`), Arvind (`arvi8080`) aur Shreyash (`Trimaxsteel`) collaborators hain.
3. **Har koi apna GitHub token banaye** (private repo clone aur push karne ke liye): GitHub → Settings → Developer
   settings → Personal access tokens → Fine-grained tokens → Generate new token → Repository access: sirf
   `rohitawspro-commits/amazon-ml-challenge-2026` → Permissions: Contents = Read and write. Token kisi ko mat bhejna.

## 2. Kaun kya karega

| Kaun | Machine | Kaam |
| --- | --- | --- |
| Rohit | Claude chat | Ulta search (reverse blocking) aur mutual-best features; sabki branches merge karna |
| Shreyash | Kaggle | v2 ki galtiyon ki analysis, phir hybrid ka cross-encoder (Kaggle GPU pe) |
| Aryan | Kaggle | Candidates kam karne wala pruning step |
| Arvind | AWS | Zyada training data wala experiment, phir final test run aur zip |

Transliteration pe kaam nahi karna: sabse mushkil copies mein sirf 1.9% naam non-Latin script mein hain
(saari copies mein 13.7%), yaani dictionary scripts ko pehle se theek sambhal leti hai.

## 3. Setup (sabke liye same)

```bash
git clone https://<github-username>:<TOKEN>@github.com/rohitawspro-commits/amazon-ml-challenge-2026.git
cd amazon-ml-challenge-2026
git checkout claude/jolly-turing-655hzw
git checkout -b <naam>/<kaam>            # jaise shreyash/error-analysis
pip install gdown -r code/business_entity_resolution/requirements.txt
gdown --folder "https://drive.google.com/drive/folders/1bcJiltepYMEGJ_A54fFM4u_LQmPbzjBt" -O data/raw/gdrive
cd data/raw && unzip -q gdrive/*_student_resource.zip && rm -rf gdrive __MACOSX && cd ../..
```

Machine mein kam se kam 16 GB RAM chahiye (training lagbhag 12 GB leti hai).

**requirements.txt:** asli pins `code/business_entity_resolution/requirements.txt` mein hain (polars, numpy 2.x,
lightgbm 4.7, sparse_dot_topn, rapidfuzz ...). Root wali file pehle khali thi, ab wo isi ko forward karti hai.
`numpy<2` pin mat lagana, hamare pins numpy 2.x ke liye hain. Cross-encoder ke liye upar se `sentence-transformers`
install karo, torch ko haath mat lagana (Kaggle ka CUDA wala torch rehne do).

## 4. Kaggle (Aryan, Shreyash)

- New Notebook → right panel mein **Accelerator: None** (ye code GPU use nahi karta) aur **Internet: On**
  (ek baar phone verification lagega). CPU session mein lagbhag 4 cores, 30 GB RAM aur 12 ghante milte hain.
- Token ko Add-ons → Secrets mein `GITHUB_TOKEN` naam se daalo, aur pehle cell mein:

  ```python
  import os
  from kaggle_secrets import UserSecretsClient
  os.environ["GITHUB_TOKEN"] = UserSecretsClient().get_secret("GITHUB_TOKEN")
  ```

  Phir setup ke commands `/tmp` mein chalao (`%cd /tmp`, phir har command ke aage `!`, token ki jagah
  `$GITHUB_TOKEN`). `/tmp` isliye, taaki token wali repo notebook ke output mein save na ho. Notebook private hi rakhna.
- Lambe run ke liye **Save Version → Save & Run All (Commit)** use karo. Isse notebook background mein 12 ghante tak
  chalta hai, chahe browser band ho jaye. Normal session idle hone pe ruk jaata hai.
- Jo result rakhna hai, use `/kaggle/working/` mein copy karo. Wo notebook ke Output tab se download ho jayega.

### Shreyash: v2 ki galtiyon ki analysis

```bash
cd code/business_entity_resolution/src
python3 train.py --tag ea --n-train 200000 --n-val 50000     # lagbhag 1 ghanta, v2 wali settings
python3 error_analysis.py --tag ea --n 25 > /kaggle/working/ea_report.txt
```

`train.py` blocking recall print karta hai. Jo sahi matches shortlist tak nahi pahunche, wo usi se pata chalenge.
Report ki galtiyon ko ye buckets mein baanto, aur har bucket ka count plus 5 examples team group mein bhejo:
- chhoote matches: shortlist se bahar / shortlist mein the par cutoff se neeche / one-to-one rule ne hataye
- galat matches: same naam alag address / same address alag business / baaki

### Aryan: candidates kam karna (pruning)

Organisers ab chhote candidate set ko final ranking mein upar rakhenge. Abhi har business ke 52.8 candidates hain.
Goal hai inhe 10–15 tak laana, aur sahi matches 0.1% se zyada nahi khone.

1. `python3 train.py --tag pr --n-train 200000 --n-val 50000 --block-only` chalao. Isse candidates aur har channel
   ke scores `data/work/` mein cache ho jayenge.
2. Sirf blocking ke scores (har channel ka cosine aur rank, kitne channels ne record dhoonda) pe ek chhota model ya
   rule banao, jo har business ke candidates ko rank kare.
3. k = 5, 10, 15, 20, 30 ke liye table banao: har business ke top-k rakhne pe kitne sahi matches bachte hain.
4. Sabse achha k chuno, aur pruning ko alag file (`src/prune.py`) mein likho. Use `train.py` aur `predict.py` mein
   jodne se pehle Rohit ki chat se baat karo, kyunki wo blocking ka code badal rahi hai.

## 5. AWS (Arvind, $117 credits)

1. **Pehle quota check karo:** AWS Console → Service Quotas → Amazon EC2 → "Running On-Demand Standard (A, C, D, H,
   I, M, R, T, Z) instances". Agar ye 32 se kam hai, to 32 vCPU ki increase request abhi daalo. Naye accounts mein
   ye aksar kam hota hai, aur approve hone mein time lag sakta hai.
2. **Instance banao:** EC2 → Launch instance → Region: Mumbai (ap-south-1) → AMI: Ubuntu Server 24.04 LTS →
   type: `c6i.8xlarge` (32 vCPU, 64 GB). Quota kam ho to `c6i.4xlarge` (16 vCPU, 32 GB) lo. Storage: 100 GB gp3.
   Key pair bana ke download karo. Security group mein SSH sirf "My IP" se allow karo.
3. **Connect aur setup:**

   ```bash
   ssh -i <key>.pem ubuntu@<public-ip>
   sudo apt update && sudo apt install -y python3-pip python3-venv unzip git tmux
   python3 -m venv ~/venv && source ~/venv/bin/activate
   # ab upar wale setup ke commands
   ```

4. **Lambe run hamesha tmux mein chalao:** `tmux new -s run`. Connection toot jaye to bhi run chalta rahega.
   Wapas aane ke liye: `tmux attach -t run`.
5. **Pehla kaam, zyada training data:** `python3 train.py --tag big --n-train 500000 --n-val 50000`. Validation
   score ko v2 (0.9654) se compare karo.
6. **Final test run** (jab final model tay ho jaye): `python3 predict.py --tag <final-tag>`. Ye 32 cores pe 4 cores
   se kai guna jaldi hoga. Phir `CLAUDE.md` wala validator chalao, `./package.sh SJCM` se zip banao, aur `scp` se
   laptop pe download karke Unstop pe upload karo. AWS se badi files seedhe download ho jaati hain, yahan chat wali
   30 MB ki limit nahi hai.
7. **Paisa:** `c6i.8xlarge` lagbhag $1.5 per ghanta ka hai (console mein asli price dekh lena). Kaam na chal raha ho
   to Instance state → **Stop** karo. Terminate mat karna, warna disk ka data chala jayega. Billing → Budgets mein
   $100 ka alert laga do.

## 6. Kaam wapas kaise dena hai

- Code badla hai to apni branch pe commit karke push karo: `git push -u origin <naam>/<kaam>`.
- `CLAUDE.md` ke Status section mein apna result 2–3 line mein likho: kya try kiya, validation pe kya aaya, aur
  har business ke kitne candidates bache.
- Rohit ki chat sabki branches merge karegi, isliye ek hi file ko do log ek saath na badlein.

## 7. Timeline

- **Aaj raat tak:** Shreyash ki error report aur cross-encoder ka validation result (`CLAUDE.md` mein "Hybrid"), Aryan ki k vs recall table, Arvind ka AWS setup aur big-data
  result, Rohit ki chat ka reverse blocking result.
- **27 Sep subah:** sab jod ke final model train karna.
- **27 Sep dopahar 3 baje tak:** AWS pe final test run shuru karna.
- **27 Sep raat 9 baje tak:** Unstop pe upload aur zip submit. Deadline raat 11:59 baje hai.

## 8. Har kisi ka AI prompt (copy-paste)

Apne AI (Claude, ChatGPT, Gemini) mein apna prompt paste karo. Agar AI repo nahi padh sakta, to is file ka text bhi
saath mein paste kar do.

### Shreyash, prompt 1: error analysis

Kaggle notebook ko shuru se hi **GPU T4 x2** pe rakho (4 CPU cores, ~29 GB RAM). Isse cross-encoder ke waqt session
restart nahi karna padega.

```
I'm on team SJCM in the Amazon ML Challenge 2026 (business entity resolution). Our code is in the GitHub repo rohitawspro-commits/amazon-ml-challenge-2026, branch claude/jolly-turing-655hzw (TEAM_SETUP.md and CLAUDE.md there have the context). I'm in a Kaggle notebook with GPU T4 x2 (4 CPU cores, ~29 GB RAM, internet on) and my GitHub token is in Kaggle Secrets as GITHUB_TOKEN.
My job is the error analysis of our current model v2 (validation macro F0.5 0.965, precision 0.984, recall 0.927).
1. Write notebook cells that clone the repo into /tmp using the token, check out the branch, run pip install gdown -r code/business_entity_resolution/requirements.txt, download the data with gdown --folder "https://drive.google.com/drive/folders/1bcJiltepYMEGJ_A54fFM4u_LQmPbzjBt" -O data/raw/gdrive, and unzip it inside data/raw.
2. Run: cd code/business_entity_resolution/src && python3 train.py --tag ea --n-train 200000 --n-val 50000, then python3 error_analysis.py --tag ea --n 25 > /kaggle/working/ea_report.txt.
3. Sort the validation errors into buckets. Missed matches: not in the shortlist / in the shortlist but below the cutoff / removed by the one-to-one rule. Wrong matches: same name different address / same address different business / other. Give counts and 5 examples per bucket, and write a short summary I can send to my team.
```

### Shreyash, prompt 2: cross-encoder (hybrid), error analysis ke baad

```
Next step after the error analysis (the plan is in CLAUDE.md under "Hybrid"). In the same Kaggle notebook (GPU T4 x2), build a cross-encoder re-ranker:
1. From the labelled candidate pairs of the train.py --tag ea run (data/work), build a training set: mostly pairs whose LightGBM probability is between 0.02 and 0.98, plus a sample of confident ones. Text per side: "name: <core> | address: <naddr>" from the normalised frames.
2. Fine-tune cross-encoder/ms-marco-MiniLM-L-6-v2 (Apache-2.0) with sentence-transformers CrossEncoder as a binary classifier: max_length 96, 1-2 epochs, lr 2e-5. Keep the validation entities out of training.
3. On validation, score the unsure pairs, blend p = (1 - w) * p_lgb + w * p_ce, and pick w and the cutoff that keep precision >= 0.984. Report macro F0.5, precision and recall against LightGBM alone.
4. Save the model in fp16, put the scoring code in src/hybrid.py, and push both to the branch shreyash/hybrid (weights with git add -f). Write the result in CLAUDE.md.
```

### Aryan: pruning

Kaggle notebook: Accelerator None (CPU), Internet On.

```
I'm on team SJCM in the Amazon ML Challenge 2026 (business entity resolution). Our code is in the GitHub repo rohitawspro-commits/amazon-ml-challenge-2026, branch claude/jolly-turing-655hzw (TEAM_SETUP.md and CLAUDE.md there have the context). I'm in a Kaggle CPU notebook (4 cores, ~30 GB RAM, internet on) and my GitHub token is in Kaggle Secrets as GITHUB_TOKEN.
My job is a candidate-pruning stage. The organisers now rank teams partly on the size of candidate_pairs.tsv (smaller is better). Our blocking gives 52.8 candidates per Source-1 entity and finds 97.7% of true matches. Goal: keep only 10-15 candidates per entity while losing at most 0.1% of the true matches.
1. Write notebook cells that clone the repo into /tmp using the token, check out the branch, install the requirements and download the data (same commands as TEAM_SETUP.md section 3).
2. Run: cd code/business_entity_resolution/src && python3 train.py --tag pr --n-train 200000 --n-val 50000 --block-only. This caches the candidates with their per-channel blocking scores in data/work/.
3. Train a small model (LightGBM on blocking scores only: each channel's cosine and rank, and how many channels found the pair) that ranks each entity's candidates. Report how many true matches are kept at top-k for k = 5, 10, 15, 20, 30 on held-out entities.
4. Put the pruning in a new file src/prune.py (a function that takes the candidate frame and returns the pruned one), push it to a branch aryan/pruning, and add the k-vs-recall table to CLAUDE.md. Do not edit train.py or predict.py; Rohit's chat will wire it in.
```

### Arvind: AWS

```
I'm on team SJCM in the Amazon ML Challenge 2026 (business entity resolution). Our code is in the GitHub repo rohitawspro-commits/amazon-ml-challenge-2026, branch claude/jolly-turing-655hzw (TEAM_SETUP.md section 5 and CLAUDE.md have the context). I have an AWS account with $117 in credits and a GitHub token.
My job is to run the heavy jobs on a big EC2 machine.
1. Guide me to check my EC2 quota "Running On-Demand Standard (A, C, D, H, I, M, R, T, Z) instances" and request 32 vCPUs if it is lower. Then launch a c6i.8xlarge (or c6i.4xlarge if the quota is lower) in ap-south-1 with Ubuntu 24.04, 100 GB gp3 and SSH only from my IP.
2. Set up Python in a venv, clone the repo with my token, check out the branch, install the requirements and download the data (TEAM_SETUP.md section 3). Use tmux for every long run.
3. Run the bigger-training experiment: cd code/business_entity_resolution/src && python3 train.py --tag big --n-train 500000 --n-val 50000, and compare its validation macro F0.5 with v2 (0.9654). Push models/lgb_big.txt and models/config_big.json with git add -f (models/ is git-ignored) to a branch arvind/big-train, and write the result in CLAUDE.md.
4. Keep the machine ready for the final test run (python3 predict.py --tag <final tag>), then run the validator, build the zip with ./package.sh SJCM, and help me download it with scp. Remind me to stop the instance whenever nothing is running.
```

### Shreyash, prompt 3: test ke unsure pairs ko cross-encoder se score karna (Cell 10 ke baad, usi notebook mein)

Rohit ki chat v4 ke test scores mein se unsure pairs (LightGBM prob 0.02 se 0.98) unke normalised text ke saath
`submissions/v4/uncertain_test_pairs_*.parquet` mein push karegi (27 Sep ~18:30 IST, branch `claude/jolly-turing-655hzw`).
Cell 10 ke baad ye cell chalao (`ce_model`, `BEST_W`, `BEST_THR`, `LO`, `HI`, `BEST_F`, `BEST_P`, `BEST_R` Cell 10 se aate hain),
phir Rohit ko batao ki branch `shreyash/hybrid` ready hai:

```python
# Cell 13 — score the uncertain TEST pairs with the fine-tuned cross-encoder and push the probabilities
import glob, json, os, subprocess, numpy as np, polars as pl, torch
os.chdir("/tmp/amazon-ml-challenge-2026")
subprocess.run(["git", "fetch", "origin", "claude/jolly-turing-655hzw"], check=True)
subprocess.run(["git", "checkout", "FETCH_HEAD", "--", "submissions/v4"], check=True)
parts = sorted(glob.glob("submissions/v4/uncertain_test_pairs_*.parquet"))
unc = pl.concat([pl.read_parquet(p) for p in parts])   # q, p, s1_id, p_id, prob, text_a, text_b
print(f"{unc.height:,} uncertain test pairs from {len(parts)} files")
with torch.no_grad():
    logits = ce_model.predict(list(zip(unc["text_a"].to_list(), unc["text_b"].to_list())),
                              batch_size=512, show_progress_bar=True, convert_to_numpy=True)
ce_prob = (1.0 / (1.0 + np.exp(-logits.astype(np.float64)))).astype(np.float32)
os.makedirs("submissions/hybrid", exist_ok=True)
unc.select("s1_id", "p_id", "prob").with_columns(ce_prob=pl.Series(ce_prob)) \
   .write_parquet("submissions/hybrid/ce_test_probs.parquet", compression="zstd")
json.dump({"w": float(BEST_W), "thr": float(BEST_THR), "lo": LO, "hi": HI,
           "val_f05": float(BEST_F), "val_prec": float(BEST_P), "val_rec": float(BEST_R)},
          open("submissions/hybrid/hybrid_params.json", "w"), indent=1)
for args in (["checkout", "-B", "shreyash/hybrid"], ["add", "-f", "submissions/hybrid"],
             ["commit", "-m", "Cross-encoder probabilities for the uncertain v4 test pairs"],
             ["push", "-u", "origin", "shreyash/hybrid", "--force"]):
    print(subprocess.run(["git", *args], capture_output=True, text=True))
```

Rohit ki chat phir `blend.py` se v4 ke scores mein blend karegi (p = (1 - w) * p_lgb + w * p_ce, sirf unsure pairs pe),
`predict.py --tag v4h --from-scores --cand-tag v4` se output likhegi, validator aur zip banayegi. Hybrid tabhi use hoga
jab validation pe wo v4 (0.9677) se better ho, precision >= 0.984 ke saath. Cell 11 (fp16 model + `hybrid.py` push)
bhi chala do, par test scoring ke liye Cell 13 kaafi hai.

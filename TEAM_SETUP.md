# Team SJCM: Kaggle aur AWS pe kaam kaise karein

Deadline: **27 Sep, 11:59 PM IST**. Poora context `CLAUDE.md` mein hai.

## 1. Sabse pehle (Rohit, abhi)

1. **Repo private karo.** Abhi repo public hai, aur isme hamara code, models aur v2 ka test output hai. Koi bhi team
   ise copy karke submit kar sakti hai. GitHub pe repo kholo, phir Settings → General → sabse neeche "Danger Zone" →
   Change visibility → Private.
2. **Teammates ko access do:** Settings → Collaborators → Add people → Aryan aur Shreyash. Arvind ke paas pehle se hai.
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
git checkout claude/quirky-cray-iffodx
git checkout -b <naam>/<kaam>            # jaise shreyash/error-analysis
pip install gdown -r code/business_entity_resolution/requirements.txt
gdown --folder "https://drive.google.com/drive/folders/1bcJiltepYMEGJ_A54fFM4u_LQmPbzjBt" -O data/raw/gdrive
cd data/raw && unzip -q gdrive/*_student_resource.zip && rm -rf gdrive __MACOSX && cd ../..
```

Machine mein kam se kam 16 GB RAM chahiye (training lagbhag 12 GB leti hai).

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

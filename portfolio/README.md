# Rohit Pujari — Cloud & DevOps Portfolio

Minimal monochrome single-page portfolio (black / charcoal / grey, Geist + Geist Mono,
1px borders) with subtle scroll reveals, a cloud architecture diagram, a CI/CD pipeline
flow, a live "self-healing incident" terminal and an **AI assistant** (Groq Llama-3) that
answers recruiter questions about Rohit's skills and projects.

Plain HTML/CSS/JS, no build step.

```
portfolio/
├── index.html
├── styles.css
├── script.js
├── api/chat.js              # serverless AI endpoint (Groq Llama-3)
└── assets/
    ├── profile.jpg          # ← add your photo here
    └── Rohit_Pujari_Resume.pdf  # ← add your resume here
```

## 1. Add your photo and resume
- Save your photo as `assets/profile.jpg` (portrait works best; it is cropped to 4:5 and
  focused slightly right of centre, shown in greyscale with colour on hover). Until it
  exists, a grey "RP" monogram is shown.
- Save your resume as `assets/Rohit_Pujari_Resume.pdf` (used by both "Resume" buttons).

## 2. Run locally
```bash
cd portfolio && python3 -m http.server 8080   # open http://localhost:8080
```
Locally the AI runs in **profile knowledge mode** (built-in answers, no API key needed).

## 3. Deploy with the live AI (Vercel, free)
1. Import the repo on vercel.com and set **Root Directory = `portfolio`**.
2. Add environment variable `GROQ_API_KEY` (free key from console.groq.com).
   Optional: `GROQ_MODEL` (default `llama-3.3-70b-versatile`).
3. Deploy. The chat badge switches to **"Groq Llama-3 · live"** when the API answers.

The API key lives only on the server; the browser never sees it. If the API is down or
rate-limited, the assistant automatically falls back to the built-in answers.

## Notes
- The contact form opens the visitor's mail client with the message pre-filled
  (no backend needed). Swap in Formspree etc. if you want in-page submission.
- The OpsMind live demo link is plain `http://`; browsers will open it fine from an
  `https://` page since it's a normal link.

# AI Risk Intelligence Engine

A hybrid fraud-risk analysis platform for digital payments, built around
explainability first: every score comes with a specific, human-readable
reason, not a black-box number.

## The problem

Payment fraud detection tools tend to fall into two failure modes: pure
rule-based systems that are transparent but rigid, or pure ML systems that
are adaptive but unexplainable and need large labeled datasets most teams
don't have. This project is a hybrid answer to that trade-off.

## How it works

```
Transaction
   │
   ▼
Input Validation (Pydantic schema, Razorpay-aligned fields)
   │
   ▼
Rule Engine ──────────┐  amount (personalized vs. user's own avg),
   │                   │  behavioral timing (day/night pattern per user),
   │                   │  geographic + payment context (country-level,
   │                   │  impossible-travel velocity, UPI/Netbanking-abroad),
   │                   │  behavior drift (trend across last 3 transactions)
   ▼                   │
User Memory (Firebase / local JSON) ◄┘  per-user history, feeds every rule above
   │
   ▼
Pattern Intelligence Engine ── learns recurring condition combinations from
   │                           past flagged transactions, matches new ones
   │                           against them, decays unused patterns, accepts
   │                           "false positive" feedback
   ▼
RAG Grounding (TF-IDF + FAISS over RBI rules / fraud typologies)
   │
   ▼
LLM Reasoning (Groq) ── turns the above into a plain-language explanation
   │
   ▼
Final Decision: risk_score, status (Cleared/Review/Suspicious), confidence
```

Every stage's output is visible in the UI, not just the final number —
including a live "which modules actually ran" pipeline indicator.

## Key features

- **Explainable scoring** — every risk factor has a specific reason, not a generic label
- **Behavioral memory per user** — amount, timing, and geography are judged against *that user's own history*, not fixed global thresholds
- **Pattern Intelligence** — learns recurring fraud-condition combinations, reinforces them on repeat, decays them if unused, and improves from human feedback ("Mark as False Positive")
- **RAG-grounded explanations** — references real RBI authentication rules and known fraud typologies (mule accounts, SIM swap, UPI collect-request scams), not invented facts
- **Batch analysis** — upload a CSV/JSON of transactions, get a ranked table, summary insights, and a CSV export; uses a cost-aware hybrid LLM strategy (full explanation for the top 5 riskiest, fast rule-based text for the rest)
- **Firebase-backed persistence** with automatic local-JSON fallback if not configured
- **Role-based auth** (Firebase Authentication) — one hardcoded admin email, everyone else who signs up gets standard access
- **Live dashboard** — Logs (searchable), User Profiles (real per-user stats + trend), Fraud Insights (dynamic %, peak fraud window, top patterns), Alerts (recent high-risk transactions)

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Flask (Python) |
| Validation | Pydantic |
| LLM | Groq (`openai/gpt-oss-20b`) |
| RAG retrieval | TF-IDF + FAISS (chosen over full embedding models to keep install size/time small) |
| Persistence | Firebase Realtime Database, with local JSON fallback |
| Auth | Firebase Authentication |
| Frontend | HTML/CSS (Tailwind) + vanilla JS, server-rendered via Jinja |

## Setup

```bash
cd ai-risk-analyst
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
```
GROQ_API_KEY=...                  # console.groq.com, free
FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
FIREBASE_DATABASE_URL=https://your-project-default-rtdb.firebaseio.com
FIREBASE_API_KEY=...              # web app config, for client-side login
FIREBASE_AUTH_DOMAIN=...
SECRET_KEY=some-random-string
```

Also required:
- A Firebase project with Realtime Database + Authentication (Email/Password) enabled
- A `serviceAccountKey.json` in the project root (Firebase Console → Project Settings → Service Accounts)
- At least one user created in Firebase Authentication to log in with

Run:
```bash
python backend/main.py
```
Open `http://127.0.0.1:5000` — you'll be redirected to `/login`.

## Project structure

```
ai-risk-analyst/
├── backend/
│   ├── main.py                   # Flask app, all routes
│   ├── models/transaction.py     # Pydantic schema
│   └── services/
│       ├── rule_engine.py        # amount/timing/geo/drift scoring
│       ├── profile_service.py    # per-user memory
│       ├── pattern_engine.py     # pattern learning/matching/decay/feedback
│       ├── aggregator.py         # combines everything into final decision
│       ├── llm_engine.py         # Groq call + prompt
│       ├── batch_processor.py    # CSV/JSON batch analysis
│       ├── log_service.py        # persistent transaction log
│       ├── firebase_client.py    # Firebase init (profiles/logs/patterns refs)
│       └── auth_service.py       # Firebase Auth token verification
├── templates/
│   ├── index.html                # dashboard (all views, JS-toggled)
│   └── login.html                # login + signup
├── static/js/app.js
├── rag/
│   ├── data/fraud_knowledge.txt  # RBI rules + fraud pattern knowledge base
│   └── retriever.py
├── memory/                       # local JSON fallback storage
├── tests/sample_batch.csv        # sample file for testing batch mode
├── TESTING_CHECKLIST.md
├── DEMO_SCRIPT.md
└── requirements.txt
```

## Known limitations (honest, not hidden)

- **Timezone handling is best-effort.** A single timestamp field can't
  reliably capture true local time for a foreign transaction, so
  personalized timing checks are skipped (not guessed) for foreign
  transactions rather than risk a wrong penalty.
- **Pattern Intelligence needs volume to be meaningful.** With a small
  demo dataset, patterns form from just a few repeats — genuinely useful
  behavior, but the frequencies won't look like production-scale data.
- **IP geolocation depends on a third-party API** (ipapi.co) with a free-tier
  rate limit; cached per-IP to minimize calls, but a large batch of unique
  IPs could hit the limit.
- **No ML anomaly-detection layer.** Deliberately not added — with this data
  volume, an unsupervised model would add noise, not signal, without
  compromising the explainability the whole design is built around.
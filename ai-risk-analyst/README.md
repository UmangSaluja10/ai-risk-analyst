# AI Risk Intelligence Engine

## Current status: Core pipeline complete + Batch Mode + polish pass

## What's built
Full pipeline: validated input → rule engine → user memory → feature
aggregation → Groq LLM reasoning → RAG grounding → confidence + pipeline
visibility → Firebase persistence (with local JSON fallback).

**This update adds:**
- **Batch Risk Analyzer** — new mode (sidebar → "Batch Analysis"), upload a
  CSV/JSON file of transactions, get a ranked risk table, summary insights,
  and a CSV export. Uses a hybrid strategy: full LLM+RAG explanations only
  for the top 5 riskiest transactions, fast rule-based text for the rest —
  keeps large files from blowing through Groq's free-tier rate limits.
- **Razorpay-aligned schema** — researched Razorpay's actual Payment entity;
  `payment_type` now uses real values (`upi`, `card`, `netbanking`, `wallet`,
  `emi`) instead of generic placeholders, and every transaction gets an
  auto-generated `payment_id` (e.g. `pay_a1b2c3...`) for traceability.
  Note: Razorpay's own API doesn't log IP/location in the core payment
  object — that's captured separately by checkout SDKs — so our `location`
  field is a reasonable custom addition, not a fabricated "official" field.
- **Auto-detected location** — the Location field on the single-transaction
  form now auto-fills with your real IP on page load (via a free geolocation
  API), defaulting to an Indian IP if detection fails. Stays editable so you
  can still manually test flagged/VPN locations for demos.
- **Cleaned up stale "Phase X" labels** that were left in the UI/backend text
  from earlier development phases.

## Project structure
```
ai-risk-analyst/
├── backend/
│   ├── main.py                   # routes: /, /analyze, /analyze_batch
│   ├── models/transaction.py     # Razorpay-aligned schema
│   ├── services/
│   │   ├── rule_engine.py
│   │   ├── profile_service.py
│   │   ├── firebase_client.py
│   │   ├── aggregator.py
│   │   ├── llm_engine.py
│   │   └── batch_processor.py    # NEW -- CSV/JSON parsing, ranking, hybrid LLM, CSV export
│   ├── routes/
│   └── utils/
├── templates/index.html          # now has singleView + batchView toggle
├── static/js/app.js
├── memory/user_profiles.json
├── serviceAccountKey.json        # you add this (Firebase), gitignored
├── rag/
├── tests/sample_batch.csv        # NEW -- sample file to test batch mode
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Batch file format
CSV or JSON, one transaction per row/object:
```
user_id,amount,location,payment_type,timestamp
USR-001,4500,103.21.58.10 (IN),upi,2026-08-23T14:30:00
```
`timestamp` is optional (defaults to now). Try `tests/sample_batch.csv` first.

## How to run
```bash
cd ai-risk-analyst
pip install -r requirements.txt
cp .env.example .env      # add Groq + Firebase config
python backend/main.py
```
Open **http://127.0.0.1:5000**

## Not built yet
- Fully dynamic sidebar (User Profiles list, Logs history, Settings pages still static)
- Scripted end-to-end test cases + final demo writeup (polish phase)
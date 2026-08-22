# AI Risk Intelligence Engine

## Current status: Phase 5 complete — LLM Reasoning Engine

## What's built so far
- **Phase 0:** Flask backend + exact dashboard UI, wired end-to-end.
- **Phase 1:** Validated transaction schema (Pydantic).
- **Phase 2:** Static rule-based scoring.
- **Phase 3:** Per-user memory (JSON-file-backed).
- **Phase 4:** Feature aggregation cleanup.
- **Phase 5:** Real LLM explanations via **Groq** (`llama-3.1-8b-instant`).
  If no API key is set, falls back to the rule-based reasons string —
  the app never breaks because of the LLM layer.

## Setup required for this phase
1. Get a free key at https://console.groq.com (no card needed)
2. Copy `.env.example` → `.env`
3. Put your real key in `.env`: `GROQ_API_KEY=gsk_...`
4. `.env` is gitignored — never commit it

## Project structure
```
ai-risk-analyst/
├── backend/
│   ├── main.py
│   ├── models/transaction.py
│   ├── services/
│   │   ├── rule_engine.py
│   │   ├── profile_service.py
│   │   ├── aggregator.py
│   │   └── llm_engine.py        # Groq call + prompt (Phase 5)
│   ├── routes/
│   └── utils/
├── templates/index.html
├── static/js/app.js
├── memory/user_profiles.json
├── rag/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## How to run
```bash
cd ai-risk-analyst
pip install -r requirements.txt
cp .env.example .env      # then edit .env with your real Groq key
python backend/main.py
```
Open **http://127.0.0.1:5000**

## Not built yet
- RAG grounding (Phase 6) — LLM currently reasons only from the transaction + scores, no external fraud-pattern documents yet
- Firebase persistence (currently local JSON file)
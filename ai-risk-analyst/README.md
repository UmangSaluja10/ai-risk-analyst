# AI Risk Intelligence Engine

## Current status: Phase 4 complete — Feature Aggregation

## What's built so far
- **Phase 0:** Flask backend + exact dashboard UI, wired end-to-end.
- **Phase 1:** Validated transaction schema (Pydantic).
- **Phase 2:** Static rule-based scoring.
- **Phase 3:** Per-user memory (JSON-file-backed).
- **Phase 4:** Cleanup — merged rule + memory outputs into one `aggregator.py`
  module. `main.py` is now: validate → rules → memory → aggregate → respond.
  No logic changed, no new behavior — this just makes the codebase clean
  enough to plug the LLM into in Phase 5.

## Project structure
```
ai-risk-analyst/
├── backend/
│   ├── main.py
│   ├── models/transaction.py
│   ├── services/
│   │   ├── rule_engine.py       # static rules (Phase 2)
│   │   ├── profile_service.py   # per-user memory (Phase 3)
│   │   └── aggregator.py        # merges rules + memory into one object (Phase 4)
│   ├── routes/
│   └── utils/
├── templates/index.html
├── static/js/app.js
├── memory/user_profiles.json
├── rag/
├── tests/
├── requirements.txt
└── README.md
```

## How to run
```bash
cd ai-risk-analyst
pip install -r requirements.txt
python backend/main.py
```
Open **http://127.0.0.1:5000**

## Not built yet
- LLM-generated explanations (Phase 5) — `aggregator.py`'s output is exactly
  what will get handed to the LLM prompt next phase, replacing the current
  concatenated-reasons string
- RAG grounding (Phase 6)
- Firebase persistence (currently local JSON file)
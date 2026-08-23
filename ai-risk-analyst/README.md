# AI Risk Intelligence Engine

## Current status: Firebase Persistence complete (built on top of Phase 7)

## What's built so far
- **Phases 0-7:** Full pipeline — validated input, rules, memory, aggregation,
  Groq LLM reasoning, RAG grounding, confidence + pipeline visibility.
- **Firebase Persistence:** User profiles can now live in Firebase Realtime
  Database instead of a local JSON file. If Firebase isn't configured, it
  automatically falls back to the local JSON file — same pattern as the
  Groq LLM fallback, so nothing breaks while you're setting it up.

## Setup required for this phase (see step card above for the click-by-click version)
1. Create a Firebase project + enable Realtime Database
2. Download a service account key → save as `serviceAccountKey.json` in project root
3. Add to `.env`:
   ```
   FIREBASE_CREDENTIALS_PATH=serviceAccountKey.json
   FIREBASE_DATABASE_URL=https://your-project-default-rtdb.firebaseio.com
   ```
4. Restart the server — check the terminal for `[firebase] Connected successfully.`
   If you see a fallback warning instead, it's using the local JSON file, which
   is fine for continued testing.

## Project structure
```
ai-risk-analyst/
├── backend/
│   ├── main.py
│   ├── models/transaction.py
│   ├── services/
│   │   ├── rule_engine.py
│   │   ├── profile_service.py   # now reads/writes Firebase OR local JSON
│   │   ├── firebase_client.py   # NEW -- Firebase init, graceful fallback
│   │   ├── aggregator.py
│   │   └── llm_engine.py
│   ├── routes/
│   └── utils/
├── templates/index.html
├── static/js/app.js
├── memory/user_profiles.json    # fallback storage if Firebase not configured
├── serviceAccountKey.json       # YOU add this, gitignored
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
cp .env.example .env      # add Groq key + Firebase config
python backend/main.py
```
Open **http://127.0.0.1:5000**

## Not built yet
- Dynamic sidebar navigation (User Profiles / Fraud Insights / Logs pages currently static links)
- Phase 8/9 polish: scripted test cases, final demo-ready writeup
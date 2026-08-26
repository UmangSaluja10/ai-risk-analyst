# AI Risk Intelligence Engine

## Current status: Full dynamic app — auth, live profiles, insights, logs, alerts, contextual risk scoring

## Latest update: smarter location/timing/payment scoring
- **Country-level location comparison, not exact-string.** Traveling to a
  different city/state/country no longer triggers a penalty by itself —
  only the *country* is compared against the user's usual country, so
  normal travel is never flagged alone.
- **New combined "Geographic & Payment Context" factor** replaces the old
  flat "new location = penalty" rule. It only scores when signals combine
  the way real fraud does:
  - Two different countries within 12 hours ("impossible travel")
  - An unusually large amount specifically for a *foreign* transaction
  - UPI/Netbanking used from outside the user's usual country (these are
    largely India-only rails — cards are the normal method for genuine
    overseas spend, so cards get little/no extra weight, wallets a little
    more, UPI/Netbanking the most)
- **Timezone honesty:** personalized day/night timing checks now only run
  for domestic (same-country) transactions. For foreign transactions, true
  local time can't be reliably inferred from a single ambiguous timestamp
  field, so that check is skipped rather than guessed — a documented
  limitation, not silently wrong behavior.
- Amount scoring (personalized vs. user's own average) already worked this
  way since Phase 7 — unchanged.

## What's built
Full pipeline (validate → rules → memory → aggregate → LLM → RAG → decision)
+ Batch Mode + Firebase persistence, and now:

- **Login / Authentication (Firebase Auth)** — email/password sign-in via
  Firebase Authentication. The login page uses the Firebase client SDK to
  sign in, then sends the ID token to the backend for verification
  (Firebase Admin SDK). `umangsaluja99@gmail.com` is hardcoded as Admin in
  `backend/services/auth_service.py`; any other authenticated email gets
  the Analyst role. **Requires** creating that user in Firebase Console →
  Authentication → Users, and pasting your Web App config into `login.html`
  (see setup steps above — the API key there is safe to expose publicly).
- **Transaction Logs** (new, foundational) — every single or batch analysis
  is now persisted (Firebase or local JSON fallback, same pattern as
  profiles). This feeds everything below.
- **User Profiles page** — real per-user data: transaction count, avg amount,
  flagged count, last active, and a mini bar-chart of their last 6 risk scores.
- **Fraud Insights page** — dynamic, computed live from logged data: % of
  transactions flagged, most common location among flagged transactions,
  and the 4-hour window with the most flagged activity (e.g. "72% ... occur
  between 1AM-5AM" style insight, generated from real data not hardcoded).
- **Logs page** — searchable table of every processed transaction (search by
  TX ID or User ID). The header search bar also jumps here and filters.
- **Alerts** — bell icon now shows a real dropdown of the 5 most recent
  Suspicious transactions, with an unread-style count badge.
- **Settings page** — Groq/Firebase connection status, version, logged-in user.

## Project structure
```
ai-risk-analyst/
├── backend/
│   ├── main.py                   # routes: /, /login, /logout, /analyze,
│   │                              #   /analyze_batch, /logs, /profiles,
│   │                              #   /insights, /system_status
│   ├── models/transaction.py
│   ├── services/
│   │   ├── rule_engine.py
│   │   ├── profile_service.py    # + get_all_profiles()
│   │   ├── firebase_client.py    # now manages 2 refs: profiles + logs
│   │   ├── log_service.py        # NEW -- persistent transaction log
│   │   ├── auth_service.py       # NEW -- hardcoded users, hashed passwords
│   │   ├── aggregator.py
│   │   ├── llm_engine.py
│   │   └── batch_processor.py    # now also writes to log_service
│   ├── routes/
│   └── utils/
├── templates/
│   ├── index.html                # singleView/batchView/logsView/profilesView/insightsView/settingsView
│   └── login.html                # NEW
├── static/js/app.js
├── memory/
│   ├── user_profiles.json
│   └── transaction_logs.json     # NEW (local fallback)
├── rag/
├── tests/sample_batch.csv
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## How to run
```bash
cd ai-risk-analyst
pip install -r requirements.txt
cp .env.example .env      # add Groq key, Firebase config, and a real SECRET_KEY
python backend/main.py
```
Open **http://127.0.0.1:5000** → you'll be redirected to `/login` first.

## Not built yet
- Per-user drill-down detail page (Profiles is currently a table, not clickable rows)
- Scripted end-to-end test cases + final demo writeup (polish phase)
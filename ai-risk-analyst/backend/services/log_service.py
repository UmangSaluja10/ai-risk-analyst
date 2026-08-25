"""
Transaction Log Storage.
Every scored transaction (single or batch) gets recorded here. This is the
shared data source for the Logs view, User Profiles view, Fraud Insights,
and the Alerts dropdown -- one write, four features read from it.
Same Firebase-with-local-JSON-fallback pattern as profile_service.
"""

import json
import os
from datetime import datetime

from services import firebase_client

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "memory", "transaction_logs.json")
MAX_LOGS = 500


def _load() -> dict:
    if firebase_client.FIREBASE_ENABLED:
        data = firebase_client.get_logs_ref().get()
        return data or {"counter": 0, "entries": {}}
    if not os.path.exists(LOG_PATH):
        return {"counter": 0, "entries": {}}
    with open(LOG_PATH, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"counter": 0, "entries": {}}


def _save(data: dict) -> None:
    if firebase_client.FIREBASE_ENABLED:
        firebase_client.get_logs_ref().set(data)
        return
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def record_log(transaction, result: dict, explanation: str) -> str:
    data = _load()
    data["counter"] = data.get("counter", 0) + 1
    tx_id = f"TX-{9000 + data['counter']}"

    entries = data.get("entries", {})
    entries[tx_id] = {
        "tx_id": tx_id,
        "payment_id": transaction.payment_id,
        "user_id": transaction.user_id,
        "amount": transaction.amount,
        "location": transaction.location,
        "payment_type": transaction.payment_type.value,
        "risk_score": result["risk_score"],
        "status": result["status"],
        "confidence": result["confidence"],
        "timestamp": transaction.timestamp.isoformat(),
        "explanation": explanation[:300],
    }

    if len(entries) > MAX_LOGS:
        oldest_first = sorted(entries.items(), key=lambda kv: kv[1]["timestamp"])
        for tid, _ in oldest_first[: len(entries) - MAX_LOGS]:
            del entries[tid]

    data["entries"] = entries
    _save(data)
    return tx_id


def get_logs(limit: int = 200) -> list[dict]:
    data = _load()
    entries = list(data.get("entries", {}).values())
    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries[:limit]


def get_logs_for_user(user_id: str, limit: int = 100) -> list[dict]:
    return [e for e in get_logs(limit=5000) if e["user_id"] == user_id][:limit]
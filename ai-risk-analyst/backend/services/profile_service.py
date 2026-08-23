"""
Phase 3: Memory Layer.
Stores per-user transaction history in a JSON file (swap for Firebase later --
just replace _load/_save with Firebase reads/writes, everything else stays the same).
"""

import json
import os
from datetime import datetime, timezone

from services import firebase_client

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "memory", "user_profiles.json")


def _load_profiles() -> dict:
    if firebase_client.FIREBASE_ENABLED:
        data = firebase_client.get_ref().get()
        return data or {}
    if not os.path.exists(PROFILE_PATH):
        return {}
    with open(PROFILE_PATH, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_profiles(data: dict) -> None:
    if firebase_client.FIREBASE_ENABLED:
        firebase_client.get_ref().set(data)
        return
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _safe_key(user_id: str) -> str:
    """Firebase Realtime DB keys can't contain . # $ [ ] / -- sanitize for storage."""
    for ch in [".", "#", "$", "[", "]", "/"]:
        user_id = user_id.replace(ch, "_")
    return user_id


def get_profile(user_id: str) -> dict:
    profiles = _load_profiles()
    return profiles.get(_safe_key(user_id), {
        "transaction_count": 0,
        "total_amount": 0,
        "avg_amount": 0,
        "locations": [],
        "first_seen": None,
    })


def evaluate_against_profile(user_id: str, location: str) -> dict:
    """
    Phase 7: amount deviation is now handled inside rule_engine.score_amount
    (dynamic, personalized). This function only checks location novelty, so
    it isn't double-counted.
    """
    profile = get_profile(user_id)

    if profile["transaction_count"] == 0:
        return {
            "location_score": 0,
            "location_reason": "New user -- no prior location history",
            "is_new_user": True,
        }

    if location not in profile["locations"]:
        location_score = 20
        location_reason = "First transaction from this location for this user"
    else:
        location_score = 0
        location_reason = "Location matches user's known locations"

    return {
        "location_score": location_score,
        "location_reason": location_reason,
        "is_new_user": False,
    }


def record_transaction(user_id: str, amount: float, location: str, timestamp: datetime) -> None:
    """Updates (or creates) the user's profile with this transaction. Call AFTER scoring."""
    key = _safe_key(user_id)
    profiles = _load_profiles()
    profile = profiles.get(key, {
        "transaction_count": 0,
        "total_amount": 0,
        "avg_amount": 0,
        "locations": [],
        "first_seen": timestamp.isoformat(),
    })

    profile["transaction_count"] += 1
    profile["total_amount"] += amount
    profile["avg_amount"] = round(profile["total_amount"] / profile["transaction_count"], 2)
    if location not in profile["locations"]:
        profile["locations"].append(location)
    if not profile.get("first_seen"):
        profile["first_seen"] = timestamp.isoformat()

    profiles[key] = profile
    _save_profiles(profiles)


def account_age_days(profile: dict) -> int:
    if not profile.get("first_seen"):
        return 0
    first_seen = datetime.fromisoformat(profile["first_seen"])
    if first_seen.tzinfo is None:
        first_seen = first_seen.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max((now - first_seen).days, 0)
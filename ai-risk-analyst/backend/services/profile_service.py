"""
Phase 3: Memory Layer.
Stores per-user transaction history in a JSON file (swap for Firebase later --
just replace _load/_save with Firebase reads/writes, everything else stays the same).
"""

import json
import os
from datetime import datetime, timezone

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "memory", "user_profiles.json")

DEVIATION_MULTIPLIER = 3  # amount > 3x user's average triggers a flag


def _load_profiles() -> dict:
    if not os.path.exists(PROFILE_PATH):
        return {}
    with open(PROFILE_PATH, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_profiles(data: dict) -> None:
    os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_profile(user_id: str) -> dict:
    profiles = _load_profiles()
    return profiles.get(user_id, {
        "transaction_count": 0,
        "total_amount": 0,
        "avg_amount": 0,
        "locations": [],
        "first_seen": None,
    })


def evaluate_against_profile(user_id: str, amount: float, location: str) -> dict:
    """Compares a NEW transaction against the user's EXISTING history (before recording it)."""
    profile = get_profile(user_id)

    if profile["transaction_count"] == 0:
        return {
            "amount_score": 0,
            "amount_reason": "New user -- no prior history to compare against",
            "location_score": 0,
            "location_reason": "New user -- no prior location history",
            "is_new_user": True,
        }

    avg = profile["avg_amount"]
    if avg > 0 and amount > avg * DEVIATION_MULTIPLIER:
        amount_score = 25
        amount_reason = f"Amount is {amount / avg:.1f}x this user's average (Rs.{avg:,.2f})"
    else:
        amount_score = 0
        amount_reason = "Amount consistent with this user's history"

    if location not in profile["locations"]:
        location_score = 20
        location_reason = "First transaction from this location for this user"
    else:
        location_score = 0
        location_reason = "Location matches user's known locations"

    return {
        "amount_score": amount_score,
        "amount_reason": amount_reason,
        "location_score": location_score,
        "location_reason": location_reason,
        "is_new_user": False,
    }


def record_transaction(user_id: str, amount: float, location: str, timestamp: datetime) -> None:
    """Updates (or creates) the user's profile with this transaction. Call AFTER scoring."""
    profiles = _load_profiles()
    profile = profiles.get(user_id, {
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

    profiles[user_id] = profile
    _save_profiles(profiles)


def account_age_days(profile: dict) -> int:
    if not profile.get("first_seen"):
        return 0
    first_seen = datetime.fromisoformat(profile["first_seen"])
    if first_seen.tzinfo is None:
        first_seen = first_seen.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max((now - first_seen).days, 0)
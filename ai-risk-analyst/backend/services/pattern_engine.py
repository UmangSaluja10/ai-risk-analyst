"""
Pattern Intelligence Engine.
Extracts discrete condition tags from each scored transaction, stores
recurring COMBINATIONS of conditions as "patterns" when a transaction is
flagged, matches future transactions against known patterns to boost their
score, decays pattern weight over time if unused, and accepts a feedback
loop (mark false positive) that weakens a pattern.

Storage: same Firebase-with-local-JSON-fallback pattern as everything else.
"""

import json
import os
import math
from datetime import datetime, timezone

from services import firebase_client

PATTERNS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "memory", "patterns.json")

DECAY_HALF_LIFE_DAYS = 14  # weight halves every 14 days of not being seen
MIN_CONDITIONS_FOR_PATTERN = 2  # a single condition alone isn't a "pattern"
MAX_PATTERN_SCORE_BONUS = 25


def _load() -> dict:
    if firebase_client.FIREBASE_ENABLED:
        data = firebase_client.get_patterns_ref().get()
        return data or {"counter": 0, "patterns": {}}
    if not os.path.exists(PATTERNS_PATH):
        return {"counter": 0, "patterns": {}}
    with open(PATTERNS_PATH, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"counter": 0, "patterns": {}}


def _save(data: dict) -> None:
    if firebase_client.FIREBASE_ENABLED:
        firebase_client.get_patterns_ref().set(data)
        return
    os.makedirs(os.path.dirname(PATTERNS_PATH), exist_ok=True)
    with open(PATTERNS_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def extract_conditions(transaction, rule_result: dict, profile_before: dict, recent_user_logs: list[dict]) -> list[str]:
    """Turns a scored transaction into a set of discrete condition tags."""
    conditions = []
    factor_scores = {f["label"]: f["score"] for f in rule_result["factors"]}

    if factor_scores.get("Amount Anomaly", 0) >= 30:
        conditions.append("high_amount")
    if factor_scores.get("Unusual Transaction Timing", 0) > 0:
        conditions.append("odd_hour")
    if factor_scores.get("Geographic & Payment Context", 0) > 0:
        conditions.append("foreign_location")
    if factor_scores.get("High-Risk Location", 0) > 0:
        conditions.append("risky_location")

    geo_factor = next((f for f in rule_result["factors"] if f["label"] == "Geographic & Payment Context"), None)
    if geo_factor and "implausible" in geo_factor.get("reason", "").lower():
        conditions.append("impossible_travel")

    if profile_before.get("transaction_count", 0) == 0:
        conditions.append("new_user")

    method = transaction.payment_type.value
    if method in ("upi", "netbanking") and "foreign_location" in conditions:
        conditions.append("upi_or_netbanking_abroad")

    # Rapid small transactions: 3+ transactions from this user in the last hour
    recent_hour_count = 0
    for log in recent_user_logs:
        try:
            log_time = datetime.fromisoformat(log["timestamp"])
            if abs((transaction.timestamp - log_time).total_seconds()) <= 3600:
                recent_hour_count += 1
        except (ValueError, TypeError):
            continue
    if recent_hour_count >= 3:
        conditions.append("rapid_repeated_transactions")

    return sorted(set(conditions))


def _pattern_key(conditions: list[str]) -> str:
    return "+".join(sorted(conditions))


def _effective_weight(pattern: dict) -> float:
    """Applies exponential decay based on time since last_seen."""
    try:
        last_seen = datetime.fromisoformat(pattern["last_seen"])
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - last_seen).total_seconds() / 86400
    except (KeyError, ValueError):
        days_since = 0
    decay = 0.5 ** (days_since / DECAY_HALF_LIFE_DAYS)
    return pattern["weight"] * decay


def match_patterns(conditions: list[str]) -> list[dict]:
    """Finds stored patterns whose condition set is fully contained in the current conditions."""
    if len(conditions) < MIN_CONDITIONS_FOR_PATTERN:
        return []

    data = _load()
    condition_set = set(conditions)
    matches = []
    for pattern_id, pattern in data.get("patterns", {}).items():
        pattern_conditions = set(pattern["conditions"])
        if pattern_conditions and pattern_conditions.issubset(condition_set):
            eff_weight = _effective_weight(pattern)
            if eff_weight >= 1:
                matches.append({**pattern, "pattern_id": pattern_id, "effective_weight": eff_weight})

    matches.sort(key=lambda p: p["effective_weight"], reverse=True)
    return matches


def score_from_matches(matches: list[dict]) -> tuple[int, str]:
    if not matches:
        return 0, "No matching historical fraud patterns."
    top = matches[:2]
    bonus = min(MAX_PATTERN_SCORE_BONUS, round(sum(m["effective_weight"] for m in top)))
    descriptions = [f"Matched Pattern {m['pattern_id']} (seen in {m['frequency']} previous flagged case{'s' if m['frequency'] != 1 else ''})" for m in top]
    return bonus, "; ".join(descriptions) + "."


def record_pattern(conditions: list[str], status: str) -> None:
    """
    Called AFTER final scoring, only for Suspicious/Review transactions.
    Creates a new pattern or reinforces (increments frequency of) an existing one.
    """
    if len(conditions) < MIN_CONDITIONS_FOR_PATTERN or status not in ("Suspicious", "Review"):
        return

    data = _load()
    key = _pattern_key(conditions)
    patterns = data.get("patterns", {})

    existing_id = next((pid for pid, p in patterns.items() if _pattern_key(p["conditions"]) == key), None)

    now = datetime.now(timezone.utc).isoformat()
    if existing_id:
        patterns[existing_id]["frequency"] += 1
        patterns[existing_id]["weight"] = min(50, patterns[existing_id]["weight"] + 3)
        patterns[existing_id]["last_seen"] = now
    else:
        data["counter"] = data.get("counter", 0) + 1
        pattern_id = f"P-{100 + data['counter']}"
        patterns[pattern_id] = {
            "conditions": conditions,
            "risk_level": "High" if status == "Suspicious" else "Medium",
            "frequency": 1,
            "weight": 5,
            "false_positive_count": 0,
            "created": now,
            "last_seen": now,
        }

    data["patterns"] = patterns
    _save(data)


def mark_false_positive_by_conditions(conditions: list[str]) -> bool:
    """Feedback loop: weakens the pattern matching this exact condition set."""
    if not conditions:
        return False
    data = _load()
    key = _pattern_key(conditions)
    patterns = data.get("patterns", {})
    matched_any = False
    for pid, p in patterns.items():
        if _pattern_key(p["conditions"]) == key:
            p["weight"] = max(0, p["weight"] - 8)
            p["false_positive_count"] = p.get("false_positive_count", 0) + 1
            matched_any = True
    data["patterns"] = patterns
    _save(data)
    return matched_any


def get_top_patterns(limit: int = 10) -> list[dict]:
    data = _load()
    patterns = [{**p, "pattern_id": pid, "effective_weight": round(_effective_weight(p), 1)} for pid, p in data.get("patterns", {}).items()]
    patterns.sort(key=lambda p: p["frequency"], reverse=True)
    return patterns[:limit]
"""
Phase 2: Rule Engine.
Static, explainable heuristics (no ML/LLM yet). Scores 0-100 with reasons.
Thresholds are sensible defaults -- tune the constants below once you have real data.
"""

RISKY_LOCATION_KEYWORDS = ["RU", "NG", "unknown", "vpn", "tor"]

ODD_HOUR_START = 22  # 10 PM
ODD_HOUR_END = 6     # 6 AM

DEVIATION_MULTIPLIER = 1.5  # ratio above user's own average where dynamic scoring kicks in


def score_amount(amount: float, user_avg: float | None = None) -> tuple[int, str]:
    """
    Phase 7 upgrade: if the user has transaction history, score continuously
    based on how far this amount deviates from THEIR average (personalized,
    not a hardcoded bracket). Falls back to static tiers for brand-new users
    with no history yet.
    """
    if user_avg and user_avg > 0:
        ratio = amount / user_avg
        if ratio <= DEVIATION_MULTIPLIER:
            return 0, f"Amount consistent with this user's average (Rs.{user_avg:,.2f})"
        score = min(45, round((ratio - 1) * 15))
        return score, f"Amount is {ratio:.1f}x this user's average (Rs.{user_avg:,.2f})"

    # Static fallback (new user, no history to personalize against)
    if amount >= 200000:
        return 45, "Very large transaction amount (no user history to compare against yet)"
    if amount >= 50000:
        return 30, "High transaction amount (no user history to compare against yet)"
    if amount >= 10000:
        return 15, "Moderate transaction amount (no user history to compare against yet)"
    return 0, "Amount within normal range"


def score_time(hour: int) -> tuple[int, str]:
    if hour >= ODD_HOUR_START or hour < ODD_HOUR_END:
        return 20, "Transaction occurred during odd hours (10PM-6AM)"
    return 0, "Transaction occurred during normal hours"


def score_location(location: str) -> tuple[int, str]:
    loc_lower = location.lower()
    if any(keyword.lower() in loc_lower for keyword in RISKY_LOCATION_KEYWORDS):
        return 30, "Transaction from a high-risk or flagged location"
    return 0, "Location not flagged as high-risk"


def evaluate(transaction, user_avg: float | None = None) -> dict:
    """
    Runs all rules against a validated Transaction object.
    user_avg (optional): this user's historical average amount, for dynamic
    personalized amount scoring (Phase 7). None/omitted = static fallback tiers.
    """
    amount_score, amount_reason = score_amount(transaction.amount, user_avg)
    time_score, time_reason = score_time(transaction.timestamp.hour)
    location_score, location_reason = score_location(transaction.location)

    total_score = min(amount_score + time_score + location_score, 100)

    if total_score >= 60:
        status = "Suspicious"
    elif total_score >= 30:
        status = "Review"
    else:
        status = "Cleared"

    factors = [
        {"label": "Amount Anomaly", "score": amount_score, "color": "error", "reason": amount_reason},
        {"label": "Odd-Hour Transaction", "score": time_score, "color": "tertiary", "reason": time_reason},
        {"label": "High-Risk Location", "score": location_score, "color": "primary", "reason": location_reason},
    ]

    reasons = [f["reason"] for f in factors if f["score"] > 0]
    if not reasons:
        reasons = ["No anomalies detected across amount, timing, or location."]

    return {
        "risk_score": total_score,
        "status": status,
        "factors": factors,
        "reasons": reasons,
    }
"""
Phase 2: Rule Engine.
Static, explainable heuristics (no ML/LLM yet). Scores 0-100 with reasons.
Thresholds are sensible defaults -- tune the constants below once you have real data.
"""

import re
from datetime import datetime

RISKY_LOCATION_KEYWORDS = ["RU", "NG", "unknown", "vpn", "tor"]

ODD_HOUR_START = 22  # 10 PM
ODD_HOUR_END = 6     # 6 AM

FOREIGN_AMOUNT_MULTIPLIER = 2  # higher bar than the domestic 1.5x -- foreign + big spend together is the real signal
IMPOSSIBLE_TRAVEL_HOURS = 12   # two different countries within this window is physically implausible


def extract_country(location: str) -> str | None:
    """Pulls a country code out of strings like '144.16.21.239 (IN)'."""
    match = re.search(r"\(([A-Za-z]{2,3})\)", location or "")
    return match.group(1).upper() if match else None

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


def score_time(hour: int, user_day_ratio: float | None = None) -> tuple[int, str]:
    """
    Phase 7-style upgrade: if we know this user's historical day/night split,
    flag DEVIATION from their own pattern, not a flat clock-time rule.
    A person who always transacts at night isn't "suspicious" for transacting
    at night -- they're suspicious if they suddenly transact at an unusual
    time FOR THEM. Falls back to a static day/night check for new users.
    """
    is_night = hour >= ODD_HOUR_START or hour < ODD_HOUR_END

    if user_day_ratio is None:
        # No history yet -- static fallback
        if is_night:
            return 20, "Transaction occurred during odd hours (10PM-6AM); no history yet to personalize this check"
        return 0, "Transaction occurred during normal hours"

    if user_day_ratio >= 0.7:
        # This user is normally a daytime transactor
        if is_night:
            return 25, f"Unusual for this user: they transact during the day {user_day_ratio:.0%} of the time, but this happened at night"
        return 0, "Transaction time consistent with this user's usual daytime pattern"

    if user_day_ratio <= 0.3:
        # This user is normally a nighttime transactor
        if not is_night:
            return 20, f"Unusual for this user: they transact at night {(1 - user_day_ratio):.0%} of the time, but this happened during the day"
        return 0, "Transaction time consistent with this user's usual nighttime pattern"

    return 0, "User has a mixed transaction-timing history; no timing anomaly detected"


def score_location(location: str) -> tuple[int, str]:
    loc_lower = location.lower()
    if any(keyword.lower() in loc_lower for keyword in RISKY_LOCATION_KEYWORDS):
        return 30, "Transaction from a high-risk or flagged location (VPN/Tor/known-risky region)"
    return 0, "Location not flagged as high-risk infrastructure"


def _majority_country(country_counts: dict) -> str | None:
    if not country_counts:
        return None
    return max(country_counts.items(), key=lambda x: x[1])[0]


def score_geo_context(transaction, profile_before: dict) -> tuple[int, str]:
    """
    Replaces the old flat 'new location = penalty' rule. Compares at COUNTRY
    granularity (not exact IP/city) so ordinary domestic travel never scores
    anything. Only escalates when signals COMBINE the way genuine fraud does:
    implausible travel speed between countries, an unusually large amount for
    a foreign transaction, or a payment rail (UPI/Netbanking) that's
    essentially India-only and rarely used for genuine overseas spend.
    """
    current_country = extract_country(transaction.location)
    home_country = _majority_country(profile_before.get("country_counts", {}))

    is_foreign = (
        home_country is not None
        and current_country is not None
        and current_country != home_country
    )

    if not is_foreign:
        return 0, "Location's country matches this user's usual country (or there's not enough history yet to compare)."

    score = 8
    reasons = [f"Transaction is from {current_country}, outside this user's usual country ({home_country})."]

    last_location = profile_before.get("last_location")
    last_timestamp = profile_before.get("last_timestamp")
    if last_location and last_timestamp:
        last_country = extract_country(last_location)
        if last_country and last_country != current_country:
            try:
                last_dt = datetime.fromisoformat(last_timestamp)
                hours_gap = abs((transaction.timestamp - last_dt).total_seconds()) / 3600
                if hours_gap < IMPOSSIBLE_TRAVEL_HOURS:
                    score += 35
                    reasons.append(
                        f"Their previous transaction was from {last_country} only {hours_gap:.1f} hours ago -- "
                        f"physically implausible travel time between countries."
                    )
            except (ValueError, TypeError):
                pass

    user_avg = profile_before.get("avg_amount") or 0
    if user_avg > 0 and transaction.amount > user_avg * FOREIGN_AMOUNT_MULTIPLIER:
        score += 15
        reasons.append(f"Amount (Rs.{transaction.amount:,.2f}) is unusually large for a transaction outside their usual country.")

    method = transaction.payment_type.value
    if method in ("upi", "netbanking"):
        score += 18
        reasons.append(f"{method.upper()} is primarily a domestic Indian payment rail -- unusual for a genuine transaction from {current_country}.")
    elif method == "wallet":
        score += 8
        reasons.append("Digital wallets see less genuine international use than cards.")
    # card: no extra penalty -- the expected, normal method for real overseas spend

    return min(score, 60), " ".join(reasons)


def evaluate(transaction, profile_before: dict) -> dict:
    """
    Runs all rules against a validated Transaction object, using the user's
    prior profile for personalized/contextual scoring (amount deviation,
    behavioral timing, and combined geographic+payment context).
    """
    user_avg = profile_before.get("avg_amount") or None
    amount_score, amount_reason = score_amount(transaction.amount, user_avg)

    current_country = extract_country(transaction.location)
    home_country = _majority_country(profile_before.get("country_counts", {}))
    is_foreign = home_country is not None and current_country is not None and current_country != home_country

    if is_foreign:
        # We can't reliably infer true local time from a single ambiguous
        # timestamp field, so we don't penalize timing for foreign
        # transactions -- the geo factor below covers this context instead.
        time_score, time_reason = 0, "Timing check skipped for foreign transactions (local time can't be reliably inferred)."
    else:
        day = profile_before.get("day_count", 0)
        night = profile_before.get("night_count", 0)
        day_ratio = day / (day + night) if (day + night) > 0 else None
        time_score, time_reason = score_time(transaction.timestamp.hour, day_ratio)

    geo_score, geo_reason = score_geo_context(transaction, profile_before)
    location_flag_score, location_flag_reason = score_location(transaction.location)

    total_score = min(amount_score + time_score + geo_score + location_flag_score, 100)

    if total_score >= 60:
        status = "Suspicious"
    elif total_score >= 30:
        status = "Review"
    else:
        status = "Cleared"

    factors = [
        {"label": "Amount Anomaly", "score": amount_score, "color": "error", "reason": amount_reason},
        {"label": "Unusual Transaction Timing", "score": time_score, "color": "tertiary", "reason": time_reason},
        {"label": "Geographic & Payment Context", "score": geo_score, "color": "tertiary", "reason": geo_reason},
        {"label": "High-Risk Location", "score": location_flag_score, "color": "primary", "reason": location_flag_reason},
    ]

    reasons = [f["reason"] for f in factors if f["score"] > 0]
    if not reasons:
        reasons = ["No anomalies detected across amount, timing, location, or payment context."]

    return {
        "risk_score": total_score,
        "status": status,
        "factors": factors,
        "reasons": reasons,
    }
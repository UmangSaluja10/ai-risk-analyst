"""
Phase 4/7: Feature Aggregation + Final Risk Decision.
Merges rule_engine + profile_service outputs into one clean object, plus
(Phase 7) a confidence rating and a pipeline-visibility summary.
"""


def _compute_confidence(profile_transaction_count: int, triggered_factor_count: int) -> str:
    """
    Confidence reflects how much we actually know about this user, not how
    risky the transaction looks. A flagged transaction from a brand-new user
    is a valid flag, but a LOWER-confidence one, since there's no history to
    personalize the amount/location checks against.
    """
    if profile_transaction_count == 0:
        return "Low"
    if profile_transaction_count < 3:
        return "Medium"
    return "High"


def aggregate(rule_result: dict, profile_eval: dict, profile_transaction_count: int = 0) -> dict:
    total_score = min(
        rule_result["risk_score"] + profile_eval["location_score"],
        100,
    )

    if total_score >= 60:
        status = "Suspicious"
    elif total_score >= 30:
        status = "Review"
    else:
        status = "Cleared"

    factors = list(rule_result["factors"]) + [
        {"label": "New Location for User", "score": profile_eval["location_score"], "color": "tertiary"},
    ]

    reasons = list(rule_result["reasons"])
    if profile_eval["location_score"] > 0:
        reasons.append(profile_eval["location_reason"])
    if profile_eval["is_new_user"]:
        reasons.append("This is this user's first recorded transaction.")

    triggered_count = sum(1 for f in factors if f["score"] > 0)
    confidence = _compute_confidence(profile_transaction_count, triggered_count)

    return {
        "risk_score": total_score,
        "status": status,
        "factors": factors,
        "reasons": reasons,
        "confidence": confidence,
    }
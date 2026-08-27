"""
Feature Aggregation + Final Risk Decision.
rule_engine.evaluate() already returns a complete score/status/factors object
(amount, timing, geographic+payment context, and location-infra flags all
combined). This module just adds the confidence rating and a small note for
brand-new users -- it no longer needs to merge in a separate profile score,
since that's now handled inside rule_engine itself.
"""


def apply_pattern_match(rule_result: dict, pattern_score: int, pattern_reason: str) -> dict:
    """
    Adds the Pattern Intelligence factor on top of the base rule_result and
    recomputes the final score/status. Kept as a separate step (not baked
    into rule_engine.evaluate) so pattern matching stays a distinct,
    swappable layer -- e.g. easy to disable/AB-test independently of the
    core rules.
    """
    total_score = min(rule_result["risk_score"] + pattern_score, 100)

    if total_score >= 60:
        status = "Suspicious"
    elif total_score >= 30:
        status = "Review"
    else:
        status = "Cleared"

    factors = list(rule_result["factors"]) + [
        {"label": "Pattern Match", "score": pattern_score, "color": "error", "reason": pattern_reason},
    ]

    reasons = list(rule_result["reasons"])
    if pattern_score > 0:
        reasons.append(pattern_reason)

    return {
        "risk_score": total_score,
        "status": status,
        "factors": factors,
        "reasons": reasons,
    }


def _compute_confidence(profile_transaction_count: int, triggered_factor_count: int) -> str:
    """
    Confidence reflects how much we actually know about this user, not how
    risky the transaction looks. A flagged transaction from a brand-new user
    is a valid flag, but a LOWER-confidence one, since there's no history to
    personalize the amount/timing/geography checks against.
    """
    if profile_transaction_count == 0:
        return "Low"
    if profile_transaction_count < 3:
        return "Medium"
    return "High"


def aggregate(rule_result: dict, is_new_user: bool, profile_transaction_count: int = 0) -> dict:
    reasons = list(rule_result["reasons"])
    if is_new_user:
        reasons.append("This is this user's first recorded transaction.")

    triggered_count = sum(1 for f in rule_result["factors"] if f["score"] > 0)
    confidence = _compute_confidence(profile_transaction_count, triggered_count)

    return {
        "risk_score": rule_result["risk_score"],
        "status": rule_result["status"],
        "factors": rule_result["factors"],
        "reasons": reasons,
        "confidence": confidence,
    }
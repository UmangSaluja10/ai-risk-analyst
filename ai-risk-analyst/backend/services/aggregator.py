"""
Phase 4: Feature Aggregation.
Takes the outputs of rule_engine (Phase 2) and profile_service (Phase 3) and
merges them into one clean, normalized object. This is the single object
everything downstream (LLM in Phase 5, RAG in Phase 6, API response) should read from.
"""


def aggregate(rule_result: dict, profile_eval: dict) -> dict:
    total_score = min(
        rule_result["risk_score"] + profile_eval["amount_score"] + profile_eval["location_score"],
        100,
    )

    if total_score >= 60:
        status = "Suspicious"
    elif total_score >= 30:
        status = "Review"
    else:
        status = "Cleared"

    factors = list(rule_result["factors"]) + [
        {"label": "Deviation from User Avg", "score": profile_eval["amount_score"], "color": "error"},
        {"label": "New Location for User", "score": profile_eval["location_score"], "color": "tertiary"},
    ]

    reasons = list(rule_result["reasons"])
    if profile_eval["amount_score"] > 0:
        reasons.append(profile_eval["amount_reason"])
    if profile_eval["location_score"] > 0:
        reasons.append(profile_eval["location_reason"])
    if profile_eval["is_new_user"]:
        reasons.append("This is this user's first recorded transaction.")

    return {
        "risk_score": total_score,
        "status": status,
        "factors": factors,
        "reasons": reasons,
    }
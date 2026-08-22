"""
AI Risk Intelligence Engine - Phase 1
Flask backend with validated transaction input (Pydantic) feeding a still-dummy
risk response. Real detection logic (rules engine) arrives in Phase 2.
"""

from flask import Flask, render_template, request, jsonify

from models.transaction import parse_transaction
from services.rule_engine import evaluate
from services import profile_service
from services.aggregator import aggregate

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Phase 1: validates the incoming transaction against the Transaction schema.
    On success, still returns a hardcoded risk response (real scoring is Phase 2) --
    but now we KNOW the data reaching that logic is clean and well-typed.
    On failure, returns 400 with specific field-level error messages.
    """
    raw_payload = request.get_json(silent=True) or {}

    transaction, errors = parse_transaction(raw_payload)
    if transaction is None:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    rule_result = evaluate(transaction)

    profile_before = profile_service.get_profile(transaction.user_id)
    profile_eval = profile_service.evaluate_against_profile(
        transaction.user_id, transaction.amount, transaction.location
    )

    result = aggregate(rule_result, profile_eval)

    # Record this transaction into the user's profile AFTER scoring, so it doesn't score against itself
    profile_service.record_transaction(
        transaction.user_id, transaction.amount, transaction.location, transaction.timestamp
    )

    response = {
        "risk_score": result["risk_score"],
        "status": result["status"],
        "explanation": "PHASE 4 (rules + memory, aggregated, no LLM yet): " + " ".join(result["reasons"]),
        "factors": result["factors"],
        "profile": {
            "avg_amount": profile_before["avg_amount"],
            "transaction_count": profile_before["transaction_count"],
            "account_age_days": profile_service.account_age_days(profile_before),
        },
    }
    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
"""
AI Risk Intelligence Engine - Phase 1
Flask backend with validated transaction input (Pydantic) feeding a still-dummy
risk response. Real detection logic (rules engine) arrives in Phase 2.
"""

import os
import sys

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from models.transaction import parse_transaction
from services.rule_engine import evaluate
from services import profile_service
from services.aggregator import aggregate
from services import llm_engine
from services import firebase_client

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "rag"))
from retriever import build_index, retrieve

load_dotenv()
firebase_client.init_firebase()
build_index()

if os.environ.get("GROQ_API_KEY"):
    print(f"[startup] GROQ_API_KEY loaded (ends in ...{os.environ['GROQ_API_KEY'][-4:]})")
else:
    print("[startup] WARNING: GROQ_API_KEY not found -- LLM will use fallback explanations. Check your .env file location and contents.")

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
    Validates the incoming transaction, runs the full pipeline (rules -> memory
    -> aggregation -> RAG -> LLM), and returns the result. Any unexpected error
    anywhere in this pipeline (e.g. a Firebase/network issue) is caught and
    returned as clean JSON instead of crashing into an HTML error page --
    the frontend can only parse JSON, so this keeps failures visible and readable
    instead of throwing a cryptic "Unexpected token '<'" parse error.
    """
    raw_payload = request.get_json(silent=True) or {}

    transaction, errors = parse_transaction(raw_payload)
    if transaction is None:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    try:
        profile_before = profile_service.get_profile(transaction.user_id)
        rule_result = evaluate(transaction, user_avg=profile_before["avg_amount"] or None)
        profile_eval = profile_service.evaluate_against_profile(transaction.user_id, transaction.location)

        result = aggregate(rule_result, profile_eval, profile_before["transaction_count"])

        rag_query = " ".join(result["reasons"]) + f" location {transaction.location} payment {transaction.payment_type.value}"
        rag_context = retrieve(rag_query, top_k=2)

        explanation = llm_engine.generate_explanation(transaction, result, rag_context)
        llm_actually_used = not explanation.startswith("PHASE 4 fallback")

        # Record this transaction into the user's profile AFTER scoring, so it doesn't score against itself
        profile_service.record_transaction(
            transaction.user_id, transaction.amount, transaction.location, transaction.timestamp
        )

        response = {
            "risk_score": result["risk_score"],
            "status": result["status"],
            "confidence": result["confidence"],
            "explanation": explanation,
            "factors": result["factors"],
            "profile": {
                "avg_amount": profile_before["avg_amount"],
                "transaction_count": profile_before["transaction_count"],
                "account_age_days": profile_service.account_age_days(profile_before),
            },
            "rag_context": [{"title": d["title"], "content": d["content"]} for d in rag_context],
            "pipeline": {
                "rule_engine": True,
                "user_profiling": True,
                "llm_reasoning": llm_actually_used,
                "rag": len(rag_context) > 0,
            },
        }
        return jsonify(response)

    except Exception as e:
        print(f"[analyze] Unexpected error: {e}")
        return jsonify({
            "error": "Server error while processing transaction",
            "details": [str(e)],
        }), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
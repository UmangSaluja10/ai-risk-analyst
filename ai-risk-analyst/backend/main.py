"""
AI Risk Intelligence Engine
Flask backend: validated input -> rule engine -> user memory -> LLM reasoning
(Groq) -> RAG grounding -> final risk decision. Also supports batch analysis
of CSV/JSON transaction files via /analyze_batch.
"""

import os
import sys
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv

from models.transaction import parse_transaction
from services.rule_engine import evaluate
from services import profile_service
from services.aggregator import aggregate
from services import llm_engine
from services import firebase_client
from services import batch_processor
from services import log_service
from services import auth_service
from services import pattern_engine
from services import aggregator

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
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me-before-any-real-deployment")


def login_required(view):
    """Redirects page routes to /login; returns 401 JSON for API routes."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            if request.path == "/" or request.path.startswith("/login"):
                return redirect(url_for("login"))
            return jsonify({"error": "Not authenticated"}), 401
        return view(*args, **kwargs)
    return wrapped


@app.route("/config")
def config():
    return jsonify({
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "databaseURL": "https://ai-risk-analyst-default-rtdb.asia-southeast1.firebasedatabase.app",
        "projectId": "ai-risk-analyst",
        "storageBucket": "ai-risk-analyst.firebasestorage.app",
        "messagingSenderId": "531384533391",
        "appId": "1:531384533391:web:81d4d067cebc3072ad4bfa",
    })


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        id_token = data.get("id_token")
        if not id_token:
            return jsonify({"success": False, "error": "No ID token provided"}), 400

        user = auth_service.verify_id_token(id_token)
        if user:
            session["username"] = user["username"]
            session["role"] = user["role"]
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Invalid or expired sign-in. Try again."}), 401
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"), role=session.get("role"))


@app.route("/analyze", methods=["POST"])
@login_required
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
        recent_user_logs = log_service.get_logs_for_user(transaction.user_id, limit=10)
        rule_result = evaluate(transaction, profile_before, recent_user_logs)
        is_new_user = profile_before["transaction_count"] == 0

        conditions = pattern_engine.extract_conditions(transaction, rule_result, profile_before, recent_user_logs)
        matches = pattern_engine.match_patterns(conditions)
        pattern_score, pattern_reason = pattern_engine.score_from_matches(matches)
        rule_result = aggregator.apply_pattern_match(rule_result, pattern_score, pattern_reason)

        result = aggregate(rule_result, is_new_user, profile_before["transaction_count"])

        rag_query = " ".join(result["reasons"]) + f" location {transaction.location} payment {transaction.payment_type.value}"
        rag_context = retrieve(rag_query, top_k=2)

        explanation = llm_engine.generate_explanation(transaction, result, rag_context)
        llm_actually_used = not explanation.startswith("Rule-based summary")

        # Learn/reinforce the pattern now that we have a final status
        pattern_engine.record_pattern(conditions, result["status"])

        # Record this transaction into the user's profile AFTER scoring, so it doesn't score against itself
        profile_service.record_transaction(
            transaction.user_id, transaction.amount, transaction.location, transaction.timestamp
        )
        tx_id = log_service.record_log(transaction, result, explanation, conditions)

        response = {
            "tx_id": tx_id,
            "risk_score": result["risk_score"],
            "status": result["status"],
            "confidence": result["confidence"],
            "explanation": explanation,
            "factors": result["factors"],
            "matched_patterns": [{"pattern_id": m["pattern_id"], "frequency": m["frequency"]} for m in matches[:2]],
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
                "pattern_intelligence": True,
            },
        }
        return jsonify(response)

    except Exception as e:
        print(f"[analyze] Unexpected error: {e}")
        return jsonify({
            "error": "Server error while processing transaction",
            "details": [str(e)],
        }), 500


@app.route("/analyze_batch", methods=["POST"])
@login_required
def analyze_batch():
    """
    Batch Risk Analyzer: accepts an uploaded CSV or JSON file of transactions,
    scores all of them, ranks by risk, and returns results + a CSV export string.
    Uses a hybrid LLM strategy (see batch_processor.py) to stay within Groq's
    free-tier rate limits on larger files.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded", "details": ["Attach a .csv or .json file under the 'file' field"]}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected", "details": []}), 400

    try:
        rows, parse_errors = batch_processor.parse_upload(file.filename, file.read())
        if not rows:
            return jsonify({"error": "Could not read any rows from file", "details": parse_errors}), 400

        result = batch_processor.process_batch(rows)
        return jsonify(result)

    except Exception as e:
        print(f"[analyze_batch] Unexpected error: {e}")
        return jsonify({"error": "Server error while processing batch", "details": [str(e)]}), 500


@app.route("/feedback/false_positive", methods=["POST"])
@login_required
def feedback_false_positive():
    data = request.get_json(silent=True) or {}
    tx_id = data.get("tx_id")
    if not tx_id:
        return jsonify({"error": "tx_id required"}), 400

    log_entry = log_service.get_log_by_tx_id(tx_id)
    if not log_entry:
        return jsonify({"error": "Transaction not found"}), 404

    pattern_engine.mark_false_positive_by_conditions(log_entry.get("conditions", []))
    log_service.mark_feedback(tx_id, "false_positive")
    return jsonify({"success": True})


@app.route("/patterns")
@login_required
def get_patterns():
    return jsonify({"patterns": pattern_engine.get_top_patterns(limit=15)})


@app.route("/logs")
@login_required
def get_logs():
    search = request.args.get("q", "").strip().lower()
    logs = log_service.get_logs(limit=300)
    if search:
        logs = [l for l in logs if search in l["tx_id"].lower() or search in l["user_id"].lower()]
    return jsonify({"logs": logs})


@app.route("/profiles")
@login_required
def get_profiles():
    profiles = profile_service.get_all_profiles()
    logs = log_service.get_logs(limit=2000)

    result = []
    for user_id, profile in profiles.items():
        user_logs = [l for l in logs if l["user_id"] == user_id]
        user_logs.sort(key=lambda l: l["timestamp"])
        flagged_count = sum(1 for l in user_logs if l["status"] in ("Suspicious", "Review"))
        recent_scores = [l["risk_score"] for l in user_logs[-6:]]
        last_active = user_logs[-1]["timestamp"] if user_logs else profile.get("first_seen")

        result.append({
            "user_id": user_id,
            "transaction_count": profile.get("transaction_count", 0),
            "avg_amount": profile.get("avg_amount", 0),
            "flagged_count": flagged_count,
            "last_active": last_active,
            "recent_scores": recent_scores,
        })

    result.sort(key=lambda r: r["last_active"] or "", reverse=True)
    return jsonify({"profiles": result})


@app.route("/insights")
@login_required
def get_insights():
    logs = log_service.get_logs(limit=1000)
    total = len(logs)
    flagged = [l for l in logs if l["status"] in ("Suspicious", "Review")]

    flagged_pct = round(len(flagged) / total * 100, 1) if total else 0

    location_counts = {}
    for l in flagged:
        location_counts[l["location"]] = location_counts.get(l["location"], 0) + 1
    top_location = max(location_counts.items(), key=lambda x: x[1])[0] if location_counts else "N/A"

    # Bucket flagged transactions into 4-hour windows to find the riskiest time band
    windows = [(0, 4, "12AM-4AM"), (4, 8, "4AM-8AM"), (8, 12, "8AM-12PM"),
               (12, 16, "12PM-4PM"), (16, 20, "4PM-8PM"), (20, 24, "8PM-12AM")]
    window_counts = {label: 0 for _, _, label in windows}
    for l in flagged:
        try:
            hour = int(l["timestamp"][11:13])
        except (ValueError, IndexError):
            continue
        for start, end, label in windows:
            if start <= hour < end:
                window_counts[label] += 1
                break
    peak_window = max(window_counts.items(), key=lambda x: x[1])[0] if flagged else "N/A"

    status_counts = {}
    for l in logs:
        status_counts[l["status"]] = status_counts.get(l["status"], 0) + 1

    return jsonify({
        "total_transactions": total,
        "flagged_pct": flagged_pct,
        "top_risky_location": top_location,
        "peak_fraud_window": peak_window,
        "status_counts": status_counts,
    })


@app.route("/system_status")
@login_required
def system_status():
    return jsonify({
        "groq_configured": bool(os.environ.get("GROQ_API_KEY")),
        "firebase_connected": firebase_client.FIREBASE_ENABLED,
        "version": "v1.0",
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
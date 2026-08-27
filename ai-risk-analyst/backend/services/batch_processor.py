"""
Batch Risk Analyzer.
Processes many transactions at once (CSV/JSON upload), ranks by risk,
and applies a cost-aware hybrid explanation strategy:
  - Top N riskiest transactions get full LLM + RAG explanations
  - The rest get fast rule-based reason strings (no LLM call)
This avoids hammering Groq's free-tier rate limits on large files.
"""

import csv
import io
import json

from models.transaction import parse_transaction
from services.rule_engine import evaluate
from services import profile_service
from services.aggregator import aggregate, apply_pattern_match
from services import llm_engine
from services import log_service
from services import pattern_engine

TOP_N_FOR_LLM = 5


def parse_upload(filename: str, raw_bytes: bytes) -> tuple[list[dict], list[str]]:
    """Parses an uploaded CSV or JSON file into a list of row dicts."""
    errors = []
    if filename.lower().endswith(".json"):
        try:
            data = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(data, dict):
                data = [data]
            return data, errors
        except Exception as e:
            return [], [f"Could not parse JSON file: {e}"]

    if filename.lower().endswith(".csv"):
        try:
            text = raw_bytes.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            return list(reader), errors
        except Exception as e:
            return [], [f"Could not parse CSV file: {e}"]

    return [], ["Unsupported file type -- please upload a .csv or .json file"]


def _summarize(scored: list[dict]) -> list[str]:
    """Generates plain-language summary insights across the flagged subset."""
    flagged = [s for s in scored if s["result"]["status"] in ("Suspicious", "Review")]
    if not flagged:
        return ["No transactions were flagged as Review or Suspicious in this batch."]

    insights = []
    timing_flagged = sum(
        1 for s in flagged
        if any(f["label"] == "Unusual Transaction Timing" and f["score"] > 0 for f in s["result"]["factors"])
    )
    if timing_flagged > 0:
        pct = round(timing_flagged / len(flagged) * 100)
        insights.append(f"{pct}% of flagged transactions had unusual timing relative to that user's own pattern.")

    location_counts = {}
    for s in flagged:
        loc = s["transaction"].location
        location_counts[loc] = location_counts.get(loc, 0) + 1
    if location_counts:
        top_location, count = max(location_counts.items(), key=lambda x: x[1])
        if count > 1:
            insights.append(f"{count} flagged transactions originated from the same location: {top_location}.")

    high_risk_count = sum(1 for s in flagged if s["result"]["status"] == "Suspicious")
    insights.append(f"{high_risk_count} of {len(scored)} total transactions were marked Suspicious.")

    return insights


def process_batch(rows: list[dict]) -> dict:
    parsed_errors = []
    scored = []

    for i, row in enumerate(rows):
        transaction, errors = parse_transaction(row)
        if transaction is None:
            parsed_errors.append({"row": i, "errors": errors})
            continue

        profile_before = profile_service.get_profile(transaction.user_id)
        # Logging happens immediately per row (not deferred) so that repeat
        # users LATER in this same file correctly see EARLIER rows via
        # get_logs_for_user -- needed for rapid-transaction / drift detection
        # to work within a single batch file, not just across separate runs.
        recent_user_logs = log_service.get_logs_for_user(transaction.user_id, limit=10)

        rule_result = evaluate(transaction, profile_before, recent_user_logs)
        is_new_user = profile_before["transaction_count"] == 0

        conditions = pattern_engine.extract_conditions(transaction, rule_result, profile_before, recent_user_logs)
        matches = pattern_engine.match_patterns(conditions)
        pattern_score, pattern_reason = pattern_engine.score_from_matches(matches)
        rule_result = apply_pattern_match(rule_result, pattern_score, pattern_reason)

        result = aggregate(rule_result, is_new_user, profile_before["transaction_count"])
        pattern_engine.record_pattern(conditions, result["status"])

        # Record immediately so later rows for the same user see an updated average
        profile_service.record_transaction(
            transaction.user_id, transaction.amount, transaction.location, transaction.timestamp
        )

        # Log immediately with the fast rule-based explanation; upgraded to a
        # full LLM explanation below for the top-N riskiest transactions.
        initial_explanation = " ".join(result["reasons"])
        tx_id = log_service.record_log(transaction, result, initial_explanation, conditions)

        scored.append({"transaction": transaction, "result": result, "tx_id": tx_id, "explanation": initial_explanation})

    # Rank riskiest first
    scored.sort(key=lambda s: s["result"]["risk_score"], reverse=True)

    # Hybrid explanation strategy: full LLM+RAG for top N, rule-based text for the rest
    from retriever import retrieve  # rag/ is on sys.path via main.py

    for idx, item in enumerate(scored):
        if idx < TOP_N_FOR_LLM:
            rag_query = " ".join(item["result"]["reasons"]) + f" location {item['transaction'].location}"
            rag_context = retrieve(rag_query, top_k=1)
            item["explanation"] = llm_engine.generate_explanation(item["transaction"], item["result"], rag_context)
            log_service.update_log_explanation(item["tx_id"], item["explanation"])

    summary_insights = _summarize(scored)

    results = [
        {
            "tx_id": s["tx_id"],
            "payment_id": s["transaction"].payment_id,
            "user_id": s["transaction"].user_id,
            "amount": s["transaction"].amount,
            "location": s["transaction"].location,
            "payment_type": s["transaction"].payment_type.value,
            "risk_score": s["result"]["risk_score"],
            "status": s["result"]["status"],
            "confidence": s["result"]["confidence"],
            "explanation": s["explanation"],
        }
        for s in scored
    ]

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=[
        "tx_id", "payment_id", "user_id", "amount", "location", "payment_type", "risk_score", "status", "confidence"
    ])
    writer.writeheader()
    for r in results:
        writer.writerow({k: r[k] for k in writer.fieldnames})

    return {
        "results": results,
        "flagged_only": [r for r in results if r["status"] in ("Suspicious", "Review")],
        "summary_insights": summary_insights,
        "parse_errors": parsed_errors,
        "total_rows": len(rows),
        "successfully_scored": len(scored),
        "csv_export": csv_buffer.getvalue(),
    }
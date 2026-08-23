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
from services.aggregator import aggregate
from services import llm_engine

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
    odd_hour_count = sum(1 for s in flagged if any("odd" in r.lower() for r in s["result"]["reasons"]))
    if odd_hour_count > 0:
        pct = round(odd_hour_count / len(flagged) * 100)
        insights.append(f"{pct}% of flagged transactions occurred during odd hours (10PM-6AM).")

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
        rule_result = evaluate(transaction, user_avg=profile_before["avg_amount"] or None)
        profile_eval = profile_service.evaluate_against_profile(transaction.user_id, transaction.location)
        result = aggregate(rule_result, profile_eval, profile_before["transaction_count"])

        # Record immediately so later rows for the same user see an updated average
        profile_service.record_transaction(
            transaction.user_id, transaction.amount, transaction.location, transaction.timestamp
        )

        scored.append({"transaction": transaction, "result": result})

    # Rank riskiest first
    scored.sort(key=lambda s: s["result"]["risk_score"], reverse=True)

    # Hybrid explanation strategy: full LLM+RAG for top N, rule-based text for the rest
    from retriever import retrieve  # rag/ is on sys.path via main.py

    for idx, item in enumerate(scored):
        if idx < TOP_N_FOR_LLM:
            rag_query = " ".join(item["result"]["reasons"]) + f" location {item['transaction'].location}"
            rag_context = retrieve(rag_query, top_k=1)
            item["explanation"] = llm_engine.generate_explanation(item["transaction"], item["result"], rag_context)
        else:
            item["explanation"] = " ".join(item["result"]["reasons"])

    summary_insights = _summarize(scored)

    results = [
        {
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
        "payment_id", "user_id", "amount", "location", "payment_type", "risk_score", "status", "confidence"
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
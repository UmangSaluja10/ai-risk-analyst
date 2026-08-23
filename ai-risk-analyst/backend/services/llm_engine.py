"""
Phase 5: LLM Reasoning Engine.
Calls Groq to turn the aggregated risk factors into a human-readable explanation.
Falls back to the rule-based reasons string if no API key is configured or the
call fails -- the app should never break because of the LLM layer.
"""

import os
from groq import Groq

MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = (
    "You are a fraud risk analyst assistant for an Indian payments company (Razorpay-style). "
    "You will be given a transaction, its calculated risk factors, and relevant fraud "
    "intelligence context documents. Write a concise, professional explanation (2-4 sentences) "
    "of why this transaction received its risk score. Reference the specific numbers and reasons "
    "given to you. If a fraud intelligence document is genuinely relevant, you may briefly "
    "reference the pattern it describes -- but do not force a connection if none of the documents "
    "clearly apply. Do not invent facts that are not in the data provided. Amounts are in INR (Rs.). "
    "Do not use markdown formatting."
)


def _build_user_prompt(transaction, result: dict, rag_context: list[dict]) -> str:
    factor_lines = "\n".join(
        f"- {f['label']}: +{f['score']}" for f in result["factors"] if f["score"] > 0
    )
    if not factor_lines:
        factor_lines = "- No individual factors were triggered."

    if rag_context:
        rag_lines = "\n".join(f"- [{d['title']}] {d['content']}" for d in rag_context)
    else:
        rag_lines = "- No relevant fraud intelligence documents found."

    return f"""Transaction details:
- User ID: {transaction.user_id}
- Amount: Rs.{transaction.amount:,.2f}
- Location: {transaction.location}
- Payment type: {transaction.payment_type.value}
- Timestamp: {transaction.timestamp.isoformat()}

Calculated risk score: {result['risk_score']} / 100
Status: {result['status']}

Triggered factors:
{factor_lines}

Raw system reasons: {"; ".join(result["reasons"])}

Relevant fraud intelligence documents (use only if genuinely applicable):
{rag_lines}

Write the explanation now."""


def generate_explanation(transaction, result: dict, rag_context: list[dict] | None = None) -> str:
    rag_context = rag_context or []
    api_key = os.environ.get("GROQ_API_KEY")
    fallback = "Rule-based summary (LLM unavailable): " + " ".join(result["reasons"])

    if not api_key:
        return fallback

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(transaction, result, rag_context)},
            ],
            temperature=0.3,
            max_tokens=600,
            reasoning_effort="low",
        )
        text = response.choices[0].message.content.strip()
        return text if text else fallback
    except Exception as e:
        return fallback + f" (LLM call failed: {e})"
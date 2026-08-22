"""
Phase 1: Transaction input schema.
Every transaction that enters the pipeline is validated against this model
before it reaches the rule engine (Phase 2) or anything downstream.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class PaymentType(str, Enum):
    WIRE_TRANSFER = "Wire Transfer"
    CRYPTO_P2P = "Crypto P2P"
    CREDIT_CARD = "Credit Card"


class Transaction(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., gt=0, description="Transaction amount in USD, must be positive")
    location: str = Field(..., min_length=1, max_length=128, description="IP address or location string")
    payment_type: PaymentType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("user_id")
    @classmethod
    def user_id_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_id cannot be blank")
        return v

    @field_validator("location")
    @classmethod
    def location_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("location cannot be blank")
        return v

    @field_validator("amount")
    @classmethod
    def amount_reasonable(cls, v: float) -> float:
        if v > 100_000_000:
            raise ValueError("amount exceeds sane upper bound (100,000,000)")
        return round(v, 2)


def parse_transaction(raw: dict) -> tuple[Transaction | None, list[str]]:
    """
    Attempts to parse+validate raw dict input into a Transaction.
    Returns (transaction, []) on success or (None, [error messages]) on failure.
    Frontend sends amount as a string (e.g. "42500" or "$42,500") -- clean it here
    before handing off to Pydantic's numeric coercion.
    """
    cleaned = dict(raw)
    if "amount" in cleaned and isinstance(cleaned["amount"], str):
        cleaned["amount"] = cleaned["amount"].replace("₹", "").replace("$", "").replace(",", "").strip()

    try:
        return Transaction(**cleaned), []
    except Exception as e:
        # pydantic ValidationError has a structured .errors(); fall back to str(e) for anything else
        if hasattr(e, "errors"):
            messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
        else:
            messages = [str(e)]
        return None, messages
"""
Phase: Firebase Persistence.
Initializes Firebase Admin SDK if credentials are configured. If not,
FIREBASE_ENABLED stays False and profile_service falls back to the local
JSON file automatically -- same pattern as the Groq LLM fallback.
"""

import os
import firebase_admin
from firebase_admin import credentials, db

FIREBASE_ENABLED = False
_profiles_ref = None
_logs_ref = None
_patterns_ref = None


def init_firebase():
    global FIREBASE_ENABLED, _profiles_ref, _logs_ref, _patterns_ref

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    database_url = os.environ.get("FIREBASE_DATABASE_URL")

    if not cred_path or not database_url:
        print("[firebase] Not configured (FIREBASE_CREDENTIALS_PATH / FIREBASE_DATABASE_URL missing). "
              "Falling back to local JSON storage.")
        return

    if not os.path.exists(cred_path):
        print(f"[firebase] Credentials file not found at {cred_path}. Falling back to local JSON storage.")
        return

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {"databaseURL": database_url})
        _profiles_ref = db.reference("user_profiles")
        _logs_ref = db.reference("transaction_logs")
        _patterns_ref = db.reference("fraud_patterns")
        FIREBASE_ENABLED = True
        print("[firebase] Connected successfully. Using Firebase Realtime Database.")
    except Exception as e:
        print(f"[firebase] Initialization failed: {e}. Falling back to local JSON storage.")


def get_ref():
    return _profiles_ref


def get_logs_ref():
    return _logs_ref


def get_patterns_ref():
    return _patterns_ref
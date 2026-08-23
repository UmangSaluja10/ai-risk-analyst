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
_db_ref = None


def init_firebase():
    global FIREBASE_ENABLED, _db_ref

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
        _db_ref = db.reference("user_profiles")
        FIREBASE_ENABLED = True
        print("[firebase] Connected successfully. Using Firebase Realtime Database for user profiles.")
    except Exception as e:
        print(f"[firebase] Initialization failed: {e}. Falling back to local JSON storage.")


def get_ref():
    return _db_ref
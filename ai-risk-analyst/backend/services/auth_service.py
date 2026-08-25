"""
Authentication via Firebase Auth (email/password).
The frontend (login.html) signs in directly with the Firebase client SDK and
sends the resulting ID token here for verification. Requires Firebase Admin
SDK to already be initialized (see firebase_client.init_firebase()) --
if Firebase isn't configured, login cannot succeed.
"""

from firebase_admin import auth as firebase_auth

# Emails in this set get the Admin role; everyone else who successfully
# authenticates via Firebase gets Analyst.
ADMIN_EMAILS = {"umangsaluja99@gmail.com"}


def verify_id_token(id_token: str) -> dict | None:
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        email = decoded.get("email")
        if not email:
            return None
        role = "Admin" if email.lower() in ADMIN_EMAILS else "Analyst"
        return {"username": email, "role": role}
    except Exception as e:
        print(f"[auth] Firebase token verification failed: {e}")
        return None
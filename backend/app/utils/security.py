import os
from fastapi import Header, HTTPException
from app.core.logging import logger
from app.config import settings, is_cloud_mode

# Global Firebase admin initialization
_firebase_initialized = False

def init_firebase_admin():
    global _firebase_initialized
    if _firebase_initialized:
        return
    try:
        from app.utils.cloud_store import init_firebase_sdk
        _firebase_initialized = init_firebase_sdk()
        if not _firebase_initialized:
            logger.warning(
                "Firebase service account not configured. Requests are allowed only when "
                "AUTH_DEV_MODE=dev, or as the dev user when AUTH_DEV_MODE=auto (local only)."
            )
    except Exception as e:
        logger.warning(f"Firebase Admin SDK initialization skipped: {e}")


def _auth_mode() -> str:
    """Normalised auth mode: 'auto' (default) | 'dev' | 'off'."""
    return (settings.AUTH_DEV_MODE or "auto").strip().lower()


def _dev_fallback_allowed(firebase_ready: bool) -> bool:
    """
    Tri-state auth policy:
    - 'dev'  -> always allow the fixed dev user (local development only).
    - 'auto' -> allow the dev user ONLY when Firebase is not configured,
                so local dev works out of the box but production with a
                service account stays strict.
    - anything else ('off', ...) -> strict; never fall back.
    """
    mode = _auth_mode()
    if mode == "dev":
        return True
    if mode == "auto":
        # On serverless (Vercel) cloud mode NEVER fall back automatically to
        # the unverified dev user — a credential misconfig must fail closed
        # instead of leaking one user's documents to every login.
        if is_cloud_mode():
            return False
        return not firebase_ready
    return False


def _dev_user() -> dict:
    return {
        "uid": settings.DEV_USER_ID,
        "email": settings.DEV_USER_EMAIL,
        "name": settings.DEV_USER_NAME,
    }


def _dev_user_from_token(token: str) -> dict:
    """Dev-only per-login isolation (NO verification — local testing only).

    When firebase-service-account.json is missing we cannot verify tokens,
    but returning one shared uid makes every email/Google account see the
    same docs/chats. Decode the JWT payload WITHOUT verification to derive
    a stable per-login uid so different logins are isolated in dev.
    NEVER use this in production — add the service account instead.
    """
    try:
        import base64
        import hashlib
        import json as _json

        parts = (token or "").split(".")
        if len(parts) < 2 or not parts[1]:
            return _dev_user()
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8", "ignore"))
        uid = payload.get("user_id") or payload.get("uid") or payload.get("sub") or ""
        email = payload.get("email") or ""
        name = payload.get("name") or ""
        if not uid and not email:
            return _dev_user()
        stable = uid or email
        short = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:12]
        return {
            "uid": f"dev-{short}",
            "email": email or f"dev-{short}@local",
            "name": name or (email.split("@")[0] if email else settings.DEV_USER_NAME),
        }
    except Exception:
        return _dev_user()


async def get_current_user(authorization: str = Header(None)) -> dict:
    init_firebase_admin()
    firebase_ready = _firebase_initialized

    if not authorization:
        # NEVER grant the shared dev user to unauthenticated requests — that
        # leaks one user's docs to every other login/browser. Only a truly
        # wide-open local dev mode (AUTH_DEV_MODE=dev) may serve it directly.
        if _auth_mode() == "dev":
            logger.warning("Dev auth fallback in use: no Authorization header provided.")
            return _dev_user()
        raise HTTPException(status_code=401, detail="Missing Authorization header. Expected 'Bearer <token>'.")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Expected 'Bearer <token>'.")

    token = parts[1]

    # If Firebase is not available we cannot verify the token. Dev-only:
    # isolate per login via unverified payload decode so different emails
    # do NOT share docs/chats. Production must add service account instead.
    if not firebase_ready:
        if _dev_fallback_allowed(False):
            per_user = _dev_user_from_token(token)
            logger.info(f"Dev auth fallback in use (unverified): uid='{per_user.get('uid')}' email='{per_user.get('email')}'. Add firebase-service-account.json for real verification.")
            return per_user
        raise HTTPException(status_code=401, detail="Authentication service unavailable. Please try again later.")

    try:
        import firebase_admin
        from firebase_admin import auth

        decoded_token = auth.verify_id_token(token)
        # Enforce email verification for email/password accounts only.
        # Google users (sign_in_provider == 'google.com') are pre-verified
        # by Google and bypass this check entirely.
        provider = (decoded_token.get("firebase") or {}).get("sign_in_provider", "")
        email_verified = decoded_token.get("email_verified", False)
        if provider == "password" and not email_verified:
            raise HTTPException(
                status_code=403,
                detail="Please verify your email first. Check your inbox for the activation link.",
            )
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email", ""),
            "name": decoded_token.get("name", "Authenticated User")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Firebase token verification failed: {e}")
        if _auth_mode() == "dev":
            logger.info("Dev auth fallback in use after token verification failure.")
            return _dev_user()
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token. Please sign in again.")

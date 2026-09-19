import json
import os

from app.config import settings, is_cloud_mode
from app.core.logging import logger


class CloudStoreError(RuntimeError):
    """Raised when a cloud persistence operation cannot be completed."""


_firebase_app = None
_firebase_ready = False
_firebase_attempted = False


def init_firebase_sdk() -> bool:
    """Initialize the single Firebase Admin default app (idempotent).

    Credentials are loaded from FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT
    (serverless — raw JSON in an env var) or from the classic
    FIREBASE_SERVICE_ACCOUNT_JSON file path. Also registers the RTDB URL and
    Storage bucket so db/storage helpers work under the same app.
    """
    global _firebase_app, _firebase_ready, _firebase_attempted
    if _firebase_ready:
        return True
    if _firebase_attempted:
        return False
    _firebase_attempted = True
    try:
        import firebase_admin
        from firebase_admin import credentials

        content = (settings.FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT or "").strip()
        if content:
            cred = credentials.Certificate(json.loads(content))
        elif settings.FIREBASE_SERVICE_ACCOUNT_JSON and os.path.exists(
            settings.FIREBASE_SERVICE_ACCOUNT_JSON
        ):
            cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
        else:
            logger.warning(
                "Firebase credentials not found (set FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT "
                "or FIREBASE_SERVICE_ACCOUNT_JSON). Cloud persistence is unavailable."
            )
            return False

        _options = {}
        if settings.FIREBASE_DATABASE_URL:
            _options["databaseURL"] = settings.FIREBASE_DATABASE_URL
        if settings.FIREBASE_STORAGE_BUCKET:
            _options["storageBucket"] = settings.FIREBASE_STORAGE_BUCKET

        _firebase_app = firebase_admin.initialize_app(cred, _options or None)
        _firebase_ready = True
        logger.info("Firebase Admin SDK initialized (cloud persistence mode).")
        return True
    except Exception as e:
        logger.error(f"Firebase Admin SDK initialization failed: {e}")
        return False


def firebase_app():
    if not init_firebase_sdk():
        raise CloudStoreError(
            "Firebase Admin SDK is not initialized. Set FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT "
            "plus FIREBASE_DATABASE_URL and FIREBASE_STORAGE_BUCKET."
        )
    return _firebase_app


# --------------------------------------------------------------------------
# Realtime Database (JSON tree — mirrors the legacy db.json model)
# --------------------------------------------------------------------------

def _rtdb_ref(node_path: str):
    from firebase_admin import db
    return db.reference(node_path, app=firebase_app())


def rtdb_get(node_path: str) -> dict:
    """Read a JSON node; never raises, returns {} when missing."""
    try:
        value = _rtdb_ref(node_path).get()
        return value if isinstance(value, dict) else {}
    except Exception as e:
        logger.warning(f"RTDB read failed at '{node_path}': {e}")
        return {}


def rtdb_set(node_path: str, value) -> None:
    """Write a JSON node; raises on failure so callers can surface errors."""
    if value is None:
        value = {}
    try:
        _rtdb_ref(node_path).set(value)
    except Exception as e:
        logger.error(f"RTDB write failed at '{node_path}': {e}")
        raise CloudStoreError(f"Failed to persist data to Firebase: {e}") from e


# --------------------------------------------------------------------------
# Firebase Cloud Storage (uploaded document blobs)
# --------------------------------------------------------------------------

def _default_bucket():
    from firebase_admin import storage
    return storage.bucket(app=firebase_app())


def blob_upload(blob_name: str, content: bytes, content_type: str = "application/octet-stream") -> None:
    try:
        _default_bucket().blob(blob_name).upload_from_string(
            content, content_type=content_type
        )
        logger.info(f"Uploaded '{blob_name}' ({len(content)} bytes) to Firebase Storage.")
    except Exception as e:
        logger.error(f"Firebase Storage upload failed '{blob_name}': {e}")
        raise CloudStoreError(f"Failed to upload file to storage: {e}") from e


def blob_download(blob_name: str) -> bytes:
    try:
        return _default_bucket().blob(blob_name).download_as_bytes()
    except Exception as e:
        logger.error(f"Firebase Storage download failed '{blob_name}': {e}")
        raise CloudStoreError(f"Failed to read file from storage: {e}") from e


def blob_delete(blob_name: str) -> None:
    try:
        _default_bucket().blob(blob_name).delete()
        logger.info(f"Deleted Firebase Storage blob '{blob_name}'.")
    except Exception as e:
        logger.warning(f"Firebase Storage delete failed '{blob_name}': {e}")


# --------------------------------------------------------------------------
# High-level helpers used by the document / vector services
# --------------------------------------------------------------------------

def get_db_sections() -> dict:
    """Return the {documents, analyses, conversations} JSON tree."""
    return {
        "documents": rtdb_get("db/documents"),
        "analyses": rtdb_get("db/analyses"),
        "conversations": rtdb_get("db/conversations"),
    }


def save_db_sections(data: dict) -> None:
    rtdb_set("db/documents", data.get("documents") or {})
    rtdb_set("db/analyses", data.get("analyses") or {})
    rtdb_set("db/conversations", data.get("conversations") or {})


def load_vectors() -> dict:
    return rtdb_get("db/vectors")


def save_vectors(data: dict) -> None:
    rtdb_set("db/vectors", data or {})
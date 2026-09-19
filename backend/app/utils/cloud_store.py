import base64
import json
import os

from app.config import (  # noqa: F401 - is_cloud_mode re-exported; callers use cloud_store.is_cloud_mode()
    is_cloud_mode,
    settings,
)
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
    FIREBASE_SERVICE_ACCOUNT_JSON file path. Also registers the RTDB URL so
    the db helpers work under the same app.
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
            "plus FIREBASE_DATABASE_URL in the deployment env."
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
# Document file blobs (base64 nodes inside Realtime Database)
#
# Firebase Cloud Storage requires the paid Blaze plan on projects created
# after mid-2023, so blobs are kept in RTDB nodes under db/doc_files/<key>
# instead — fully free on Spark. Base64 inflates ~33%, and a single RTDB node
# holds ~32MB, which is far beyond any practical legal document here.
# --------------------------------------------------------------------------


def _blob_node_name(blob_name: str) -> str:
    # RTDB path segments cannot contain '#', '$', '[', ']', '.', or '/'.
    return base64.urlsafe_b64encode(blob_name.encode("utf-8")).decode("ascii")


def blob_upload(
    blob_name: str, content: bytes, content_type: str = "application/octet-stream"
) -> None:
    try:
        rtdb_set(
            f"db/doc_files/{_blob_node_name(blob_name)}",
            {
                "content": base64.b64encode(content).decode("ascii"),
            },
        )
        logger.info(f"Persisted '{blob_name}' ({len(content)} bytes) to Firebase RTDB.")
    except CloudStoreError as e:
        raise CloudStoreError(f"Failed to persist file '{blob_name}': {e}") from e
    except Exception as e:
        logger.error(f"Failed to persist file '{blob_name}': {e}")
        raise CloudStoreError(f"Failed to persist file: {e}") from e


def blob_download(blob_name: str) -> bytes:
    node = rtdb_get(f"db/doc_files/{_blob_node_name(blob_name)}")
    encoded = node.get("content") if isinstance(node, dict) else None
    if not encoded:
        raise CloudStoreError(f"File not found in persistence: {blob_name}")
    try:
        return base64.b64decode(encoded)
    except Exception as e:
        raise CloudStoreError(f"Failed to decode stored file '{blob_name}': {e}") from e


def blob_delete(blob_name: str) -> None:
    try:
        _rtdb_ref(f"db/doc_files/{_blob_node_name(blob_name)}").delete()
        logger.info(f"Deleted persisted file blob '{blob_name}'.")
    except Exception as e:
        logger.warning(f"Failed to delete persisted file blob '{blob_name}': {e}")


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

import os
import tempfile

from fastapi import APIRouter

from app.config import settings, is_cloud_mode, get_gemini_keys
from app.utils import cloud_store
from app.core.logging import logger

router = APIRouter()


@router.get("/debug/persistence")
def persistence_diagnostics():
    """Minimal non-secret runtime diagnostics for serverless debugging."""
    result = {
        "is_cloud_mode": is_cloud_mode(),
        "storage_backend": settings.STORAGE_BACKEND,
        "database_url_set": bool(settings.FIREBASE_DATABASE_URL),
        "service_account_content_set": bool(
            (settings.FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT or "").strip()
        ),
        "service_account_content_chars": len(
            (settings.FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT or "").strip()
        ),
        "gemini_keys": len(get_gemini_keys()),
    }

    # Firebase SDK + RTDB round-trip probe (writes then deletes a probe node).
    try:
        result["firebase_sdk_initialized"] = cloud_store.init_firebase_sdk()
        if is_cloud_mode():
            probe = cloud_store.rtdb_set("db/_probe", {"ok": True})
            result["rtdb_write_ok"] = probe is None
            result["rtdb_read_back_ok"] = cloud_store.rtdb_get("db/_probe").get("ok") is True
            try:
                cloud_store._rtdb_ref("db/_probe").delete()
            except Exception:
                pass
        else:
            result["rtdb_write_ok"] = None
            result["rtdb_read_back_ok"] = None
    except Exception as e:  # pragma: no cover - diagnostic only
        logger.error(f"Persistence probe failed: {e}")
        result["rtdb_probe_error"] = str(e)

    # Filesystem probe (extraction writes to the temp dir).
    try:
        td = tempfile.gettempdir()
        p = os.path.join(td, "legallens_probe.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ok")
        result["tmpdir_writable"] = os.path.exists(p)
        try:
            os.remove(p)
        except Exception:
            pass
        result["tmpdir"] = td
    except Exception as e:
        result["tmpdir_writable"] = False
        result["tmpdir_error"] = str(e)

    return result
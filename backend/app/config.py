import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute backend directory so env files, uploads and data resolve
# correctly regardless of the process working directory.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(_BACKEND_DIR, ".env"),
        extra="ignore",
    )

    PROJECT_NAME: str = "LegalLens AI Backend"
    VERSION: str = "1.0.0"
    PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    # Comma-separated additional allowed CORS origins (beyond FRONTEND_ORIGIN),
    # e.g. a staging mirror. Used to tighten cross-origin access in cloud mode
    # where the wildcard *.vercel.app regex would otherwise be too broad.
    CORS_ALLOWED_ORIGINS: str = ""

    # Gemini API Configuration.
    # Single key (backward compatible) and/or numbered keys GEMINI_API_KEY_2,
    # GEMINI_API_KEY_3, ... The backend rotates through all configured keys
    # and fails over to the next one when a key hits its quota/rate limit.
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    GEMINI_API_KEYS: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"

    # Firebase Configuration (resolved to an absolute path below)
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.path.join(_BACKEND_DIR, "firebase-service-account.json")

    # Auth mode:
    #   "auto" (default) -> strict token verification when Firebase is configured;
    #                       dev fallback user ONLY when no service account is present.
    #   "on"             -> always allow the dev fallback user when verification fails.
    #   "off"            -> strict mode: unauthenticated/invalid requests are rejected.
    AUTH_DEV_MODE: str = "auto"
    DEV_USER_ID: str = "usr-legallens-dev"
    DEV_USER_EMAIL: str = "dev@legallens.ai"
    DEV_USER_NAME: str = "LegalLens Dev User"

    # Upload Storage (absolute, normalised paths)
    UPLOAD_DIR: str = os.path.join(_BACKEND_DIR, "uploads")
    DATA_DIR: str = os.path.join(_BACKEND_DIR, "data")
    MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024  # 20MB limit

    # Storage backend:
    #   "local" (default) -> on-disk db.json, uploads/, embedded Qdrant.
    #   "cloud"           -> Firebase Realtime Database only (JSON tree +
    #                        base64 file nodes). Free on the Spark plan and
    #                        ideal for Vercel serverless (ephemeral, read-only
    #                        FS). No Firebase Storage bucket is required.
    STORAGE_BACKEND: str = "local"

    # Firebase Admin credentials. Use the JSON CONTENT on serverless (env var),
    # the PATH for local file-based setups. Cloud storage needs:
    #   FIREBASE_DATABASE_URL:  https://<project>-default-rtdb.firebaseio.com
    # Optional (Kept for future scale-out, unused by the RTDB-only backend):
    #   FIREBASE_STORAGE_BUCKET: <project>.firebasestorage.app
    FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT: str = ""
    FIREBASE_DATABASE_URL: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""

    # Rate limiting
    RATE_LIMIT_MAX_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60


settings = Settings()

# Resolve the Firebase service-account path relative to the backend dir when
# a relative path is configured, so auth works regardless of CWD.
if settings.FIREBASE_SERVICE_ACCOUNT_JSON and not os.path.isabs(
    settings.FIREBASE_SERVICE_ACCOUNT_JSON
):
    _candidate = os.path.join(_BACKEND_DIR, settings.FIREBASE_SERVICE_ACCOUNT_JSON)
    # Prefer the backend-relative file when it exists; otherwise keep the
    # configured value untouched.
    if os.path.exists(_candidate):
        settings.FIREBASE_SERVICE_ACCOUNT_JSON = _candidate


def _clean_key(value: str) -> str:
    """Strip whitespace/quotes; ignore placeholders."""
    cleaned = (value or "").strip().strip('"').strip("'").strip()
    if not cleaned or cleaned == "your_gemini_api_key_here":
        return ""
    return cleaned


def get_gemini_keys() -> list:
    """All configured Gemini API keys in priority order (deduped)."""
    keys: list = []
    for raw in [
        settings.GEMINI_API_KEY,
        settings.GEMINI_API_KEY_2,
        settings.GEMINI_API_KEY_3,
        *[k.strip() for k in (settings.GEMINI_API_KEYS or "").split(",")],
    ]:
        cleaned = _clean_key(raw)
        if cleaned and cleaned not in keys:
            keys.append(cleaned)
    return keys


def is_gemini_configured() -> bool:
    return bool(get_gemini_keys())


def is_cloud_mode() -> bool:
    """True when persistence must go through Firebase (Vercel serverless).

    Engaged when STORAGE_BACKEND=cloud, OR automatically when running on
    Vercel (VERCEL env is always set there) so a misconfigured deploy never
    silently uses the ephemeral local filesystem.
    """
    if (settings.STORAGE_BACKEND or "").strip().lower() == "cloud":
        return True
    return bool(os.environ.get("VERCEL"))


# Ensure local directories exist (skipped in cloud/serverless mode — the
# deployment filesystem is read-only and ephemeral).
if not is_cloud_mode():
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.DATA_DIR, exist_ok=True)

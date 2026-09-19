from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings, is_cloud_mode
from app.api.routes.health import router as health_router
from app.api.routes.documents import router as documents_router
from app.api.routes.chat import router as chat_router
from app.api.routes.general_chat import router as general_chat_router
from app.core.logging import logger
from app.core.rate_limit import RateLimitMiddleware


def _reconcile_vector_index() -> None:
    """Startup self-healing: reindex uploads missing from the vector DB.

    Guarantees every stored document is searchable (chatbot + legal advisor)
    even if vectors were lost (restart, failed indexing, store reset).
    Runs in a background thread so startup is never blocked.
    """
    try:
        from app.services.document_service import DocumentManager, _load_db
        from app.services.ai.vector_service import VectorDatabaseService

        db = _load_db()
        repaired = 0
        for doc_id, entry in list(db.get("documents", {}).items()):
            user_id = entry.get("user_id")
            if not doc_id or not user_id:
                continue
            try:
                count = VectorDatabaseService.count_document_vectors(user_id, doc_id)
            except Exception as e:
                logger.warning(f"Vector health check skipped for {doc_id} ({e}).")
                continue
            if count > 0:
                continue
            try:
                if DocumentManager.index_document(doc_id, user_id):
                    repaired += 1
                    logger.info(f"Startup reindex repaired vectors for document {doc_id}.")
            except Exception as e:
                logger.warning(f"Startup reindex failed for document {doc_id} ({e}).")
        if repaired:
            logger.info(f"Startup vector reconciliation repaired {repaired} document(s).")
    except Exception as e:
        logger.warning(f"Startup vector reconciliation skipped ({e}).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On Vercel (cloud mode): surface any Firebase credential misconfig at
    # startup and skip the startup vector reconciliation (vectors are already
    # persisted in Firebase RTDB and would otherwise be re-embedded on every
    # cold start).
    if is_cloud_mode():
        from app.utils.cloud_store import init_firebase_sdk
        if init_firebase_sdk():
            logger.info("Cloud persistence ready (Firebase RTDB + Storage).")
        else:
            logger.error(
                "Cloud persistence NOT ready. Set FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT, "
                "FIREBASE_DATABASE_URL and FIREBASE_STORAGE_BUCKET in the deployment env."
            )
        yield
        return

    import threading
    thread = threading.Thread(target=_reconcile_vector_index, daemon=True)
    thread.start()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="LegalLens AI Phase 4 — RAG + Ask LegalLens Backend",
    lifespan=lifespan,
)

# CORS setup for Vite / React frontend clients
# allow_origin_regex covers localhost, 127.0.0.1 AND any LAN IP (e.g.
# http://192.168.x.x:3000) because Vite binds --host=0.0.0.0 — a static
# allow-list would reject the browser's preflight OPTIONS with 400 and
# every authenticated request would fail. Cloud deployments (any *.vercel.app)
# are also allowed so a separately-hosted frontend can reach the API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"https?://([\w-]+\.)*vercel\.app|"
        r"http://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|localhost|0\.0\.0\.0|\[::1\])(:\d+)?"
    ),
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware (per-client IP, sliding window)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)

# Mount Routers under /api prefix
app.include_router(health_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(general_chat_router, prefix="/api")

# Serve the built React app when a dist/ (or public/) build exists next to the
# backend. Keeps /api routes untouched; everything else falls back to the SPA
# shell so client-side routing works on deep links / refresh. On local dev
# without a build this simply never activates.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_DIR = next(
    (d for d in (_REPO_ROOT / "dist", _REPO_ROOT / "public") if (d / "index.html").is_file()),
    None,
)
if _FRONTEND_DIR is not None:
    _assets_dir = _FRONTEND_DIR / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str):
        target = (_FRONTEND_DIR / full_path).resolve()
        try:
            target.relative_to(_FRONTEND_DIR.resolve())
        except ValueError:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        if target.is_file():
            return FileResponse(target)
        return FileResponse(_FRONTEND_DIR / "index.html")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global unhandled exception on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)

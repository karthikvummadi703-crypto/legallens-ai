from fastapi import APIRouter

from app.config import get_gemini_keys, is_gemini_configured, settings

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "gemini_configured": is_gemini_configured(),
        "gemini_keys_configured": len(get_gemini_keys()),
    }

from app.config import is_cloud_mode
from app.config import settings as backend_settings
from app.utils.security import _dev_fallback_allowed


def test_dev_mode_always_allows_fallback(monkeypatch):
    monkeypatch.setattr(backend_settings, "AUTH_DEV_MODE", "dev")
    assert _dev_fallback_allowed(firebase_ready=False) is True


def test_off_mode_never_allows_fallback(monkeypatch):
    monkeypatch.setattr(backend_settings, "AUTH_DEV_MODE", "off")
    assert _dev_fallback_allowed(firebase_ready=False) is False


def test_auto_allows_only_when_firebase_unset(monkeypatch):
    monkeypatch.setattr(backend_settings, "AUTH_DEV_MODE", "auto")
    assert _dev_fallback_allowed(firebase_ready=False) is True
    assert _dev_fallback_allowed(firebase_ready=True) is False


def test_cloud_mode_never_falls_back(monkeypatch):
    """A credential misconfig on serverless must fail closed, never leak."""
    monkeypatch.setattr(backend_settings, "AUTH_DEV_MODE", "auto")
    monkeypatch.setenv("VERCEL", "1")
    assert is_cloud_mode() is True
    assert _dev_fallback_allowed(firebase_ready=False) is False

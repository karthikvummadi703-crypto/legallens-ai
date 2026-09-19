from app.config import is_cloud_mode, settings


def test_default_storage_backend_is_local():
    assert settings.STORAGE_BACKEND.lower() == "local"


def test_cloud_mode_via_storage_backend(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "cloud")
    monkeypatch.delenv("VERCEL", raising=False)
    assert is_cloud_mode() is True


def test_cloud_mode_via_vercel_env(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local", prepend=False)
    monkeypatch.setenv("VERCEL", "1")
    assert is_cloud_mode() is True


def test_cloud_mode_turned_off_locally(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "local", prepend=False)
    assert is_cloud_mode() is False


def test_gemini_keys_are_deduped(monkeypatch):
    from app.config import get_gemini_keys

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "abc")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_2", "abc")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_3", '"def"')
    keys = get_gemini_keys()
    assert len(keys) == len(set(keys))
    assert "abc" in keys and "def" in keys


def test_placeholders_are_ignored(monkeypatch):
    from app.config import get_gemini_keys

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "your_gemini_api_key_here")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_2", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY_3", "")
    assert get_gemini_keys() == []

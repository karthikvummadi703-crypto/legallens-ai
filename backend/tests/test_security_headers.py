from fastapi.testclient import TestClient

from app.main import app


def test_security_headers_present():
    r = TestClient(app).get("/")
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in r.headers.get("permissions-policy", "")


def test_health_endpoint_does_not_leak_secrets():
    body = TestClient(app).get("/api/health").text
    for secret in ("AIza", "AQ.Ab8", "private_key", "client_email"):
        assert secret not in body


def test_debug_endpoint_does_not_leak_credentials():
    body = TestClient(app).get("/api/debug/persistence").text
    for secret in ("AIza", "AQ.Ab8", "private_key", "-----BEGIN", "GEMINI_API_KEY="):
        assert secret not in body

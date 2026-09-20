from fastapi.testclient import TestClient

from app.main import app


def test_security_headers_present():
    r = TestClient(app).get("/")
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in r.headers.get("permissions-policy", "")


def test_content_security_policy_present():
    r = TestClient(app).get("/")
    csp = r.headers.get("content-security-policy", "")
    # Injection defence must be active on every response.
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    # The app's real needs stay enabled (Vite bundle, inline-style React
    # attributes, Google Fonts, Firebase Auth token exchange).
    assert "script-src 'self'" in csp
    assert "font-src 'self' data: https://fonts.gstatic.com" in csp
    assert "connect-src 'self' https://*.googleapis.com" in csp


def test_hsts_header_present():
    r = TestClient(app).get("/")
    hsts = r.headers.get("strict-transport-security", "")
    assert hsts.startswith("max-age=31536000")
    assert "includeSubDomains" in hsts


def test_csp_applied_to_api_responses_too():
    r = TestClient(app).get("/api/health")
    assert "default-src 'self'" in r.headers.get("content-security-policy", "")


def test_health_endpoint_does_not_leak_secrets():
    body = TestClient(app).get("/api/health").text
    for secret in ("AIza", "AQ.Ab8", "private_key", "client_email"):
        assert secret not in body


def test_debug_endpoint_does_not_leak_credentials():
    body = TestClient(app).get("/api/debug/persistence").text
    for secret in ("AIza", "AQ.Ab8", "private_key", "-----BEGIN", "GEMINI_API_KEY="):
        assert secret not in body

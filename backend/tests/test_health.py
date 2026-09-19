import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "service" in body and "version" in body


def test_api_docs_available(client):
    assert client.get("/docs").status_code == 200


def test_unknown_route_serves_spa_fallback(client):
    # Single-function deployment: unmatched paths fall back to the SPA shell.
    r = client.get("/api/does-not-exist")
    assert r.status_code == 200


def test_root_returns_frontend(client):
    r = client.get("/")
    assert r.status_code == 200

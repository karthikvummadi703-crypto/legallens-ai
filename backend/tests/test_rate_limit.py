from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import RateLimitMiddleware


def _make_client(max_requests=3):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, max_requests=max_requests, window_seconds=60)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return TestClient(app)


def test_rate_limit_enforced():
    client = _make_client(max_requests=3)
    for _ in range(3):
        assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429


def test_rate_limit_window_slides():
    client = _make_client(max_requests=2)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429


def test_rate_limit_exempts_health():
    client = _make_client(max_requests=1)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").status_code == 200

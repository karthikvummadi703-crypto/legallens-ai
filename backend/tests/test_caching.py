import pytest
from fastapi.testclient import TestClient

from app.main import _FRONTEND_DIR, app


def test_spa_shell_is_not_cached():
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "no-cache" in r.headers.get("cache-control", "")


@pytest.mark.skipif(
    _FRONTEND_DIR is None or not (_FRONTEND_DIR / "assets").is_dir(),
    reason="frontend build not present",
)
def test_hashed_assets_are_cacheable_immutable():
    client = TestClient(app)
    assets = sorted((_FRONTEND_DIR / "assets").iterdir())
    assert assets, "expected built assets"
    r = client.get(f"/assets/{assets[0].name}")
    assert r.status_code == 200
    headers = r.headers.get("cache-control", "")
    assert "max-age=31536000" in headers
    assert "immutable" in headers

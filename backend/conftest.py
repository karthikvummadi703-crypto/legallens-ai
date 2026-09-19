"""Pytest bootstrap: make `app.*` importable when running from the repo root.

Allows `pytest backend/tests/` (or plain `pytest`) to work without manually
setting PYTHONPATH=backend.
"""

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# --- Hermetic tests: never hit the live Gemini API from unit tests ---------
# Developers may have real keys in backend/.env; unit tests must stay offline
# and deterministic, exercising the grounded fallback engines instead.
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _disable_live_gemini_keys(monkeypatch):
    try:
        from app.services.ai import gemini_keys as _gk
    except Exception:
        return
    monkeypatch.setattr(_gk.gemini_key_manager, "has_keys", lambda: False)
    monkeypatch.setattr(_gk.gemini_key_manager, "iter_keys", lambda: iter(()))

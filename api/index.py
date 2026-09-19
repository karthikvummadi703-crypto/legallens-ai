"""Vercel serverless entrypoint (classic /api convention).

Re-exports the FastAPI application from the backend package so Vercel's
Python runtime serves the whole LegalLens AI app (REST API + SPA fallback)
from a single function. The /api directory convention is what Vercel's CLI
reliably discovers for Python serverless functions.
"""
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _path in (_REPO_ROOT, os.path.join(_REPO_ROOT, "backend")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from app.main import app  # noqa: E402

__all__ = ["app"]
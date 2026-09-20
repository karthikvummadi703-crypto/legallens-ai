import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import app.config as config
import app.services.ai.vector_service as vector_service
import app.services.document_service as document_service


@pytest.fixture(autouse=True)
def isolate_storage(monkeypatch, tmp_path):
    """Keep every test hermetic.

    The app keeps process-global state and on-disk files (db.json, the vector
    snapshot, the embedded Qdrant index under `backend/data/`). Without
    isolation that state leaks across tests AND across runs, which previously
    produced order/environment-dependent failures (e.g. a leftover indexed
    document changing RAG answers). Each test therefore gets:
      - a fresh DATA_DIR / UPLOAD_DIR / DB path under tmp_path,
      - an empty in-memory vector store with the snapshot cache reset,
      - Qdrant forced off so retrieval always exercises the deterministic
        in-memory cosine store.
    """
    data_dir = tmp_path / "data"
    uploads_dir = tmp_path / "uploads"
    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config.settings, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(config.settings, "UPLOAD_DIR", str(uploads_dir))
    monkeypatch.setattr(document_service, "DB_FILE_PATH", str(data_dir / "db.json"))
    vector_service._in_memory_store.clear()
    vector_service._memory_snapshot_loaded = False
    monkeypatch.setattr(vector_service, "_qdrant_client", False)
    document_service._reset_db_cache()
    yield

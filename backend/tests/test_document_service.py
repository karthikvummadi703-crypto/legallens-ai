import os

from app.services.document_service import _load_db, _save_db, DB_FILE_PATH


def test_local_db_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.document_service.DB_FILE_PATH", str(tmp_path / "db.json"))
    payload = {"documents": {"a": {"id": 1}}, "analyses": {}, "conversations": {}}
    _save_db(payload)
    data = _load_db()
    assert data["documents"]["a"]["id"] == 1


def test_load_db_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.document_service.DB_FILE_PATH", str(tmp_path / "nope.json"))
    data = _load_db()
    assert data == {"documents": {}, "analyses": {}, "conversations": {}}


def test_load_db_corrupt_backs_up(monkeypatch, tmp_path):
    target = tmp_path / "db.json"
    target.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr("app.services.document_service.DB_FILE_PATH", str(target))
    data = _load_db()
    assert data == {"documents": {}, "analyses": {}, "conversations": {}}
    assert os.path.exists(str(target) + ".corrupt.bak")
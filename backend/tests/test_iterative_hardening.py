"""Tests locking in the iterative hardening changes.

Covers the new local DB cache in document_service, the vectorised in-memory
search equivalence in vector_service, and the de-duplicated conversation
history fetch in rag_service — so future refactors can't silently regress them.
"""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.ai import rag_service as rag_module
from app.services.ai import vector_service
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.rag_service import RAGService
from app.services.document_service import _load_db, _reset_db_cache, _save_db

# --- document_service._load_db cache -----------------------------------------


def test_db_cache_save_refreshes_read(monkeypatch, tmp_path):
    path = tmp_path / "data" / "db.json"
    monkeypatch.setattr("app.services.document_service.DB_FILE_PATH", str(path))
    _reset_db_cache()
    data = _load_db()
    data["documents"]["doc-1"] = {"user_id": "u1"}
    _save_db(data)
    again = _load_db()
    # What we saved is what we read back (cache refreshed by the save).
    assert again["documents"]["doc-1"] == {"user_id": "u1"}


def test_db_cache_never_serves_other_path(monkeypatch, tmp_path):
    path_a = tmp_path / "a"
    path_b = tmp_path / "b"
    path_a.mkdir()
    path_b.mkdir()
    monkeypatch.setattr("app.services.document_service.DB_FILE_PATH", str(path_a / "db.json"))
    _reset_db_cache()
    data = _load_db()
    data["documents"]["only-a"] = {"user_id": "u1"}
    _save_db(data)
    monkeypatch.setattr("app.services.document_service.DB_FILE_PATH", str(path_b / "db.json"))
    _reset_db_cache()
    data_b = _load_db()
    assert "only-a" not in data_b["documents"]


# --- vector_service in-memory search ------------------------------------------


class TestBedStorePayload:
    """Seeds the in-memory vector store with deterministic embeddings."""

    @staticmethod
    def seed(store, texts, doc_id="doc-1", user="user-x"):
        store.clear()
        for i, t in enumerate(texts):
            vec = EmbeddingService.generate_embedding(t, is_query=False)
            store[f"chk-{i}"] = {
                "vector": vec,
                "payload": {
                    "chunk_id": f"chk-{i}",
                    "document_id": doc_id,
                    "document_name": "agreement.txt",
                    "user_id": user,
                    "page_number": 1,
                    "section": "General",
                    "clause_id": "",
                    "text": t,
                },
            }
        return doc_id, user


def test_memory_search_numpy_matches_pure_python(monkeypatch):
    texts = [
        "The termination notice period is 30 days.",
        "The base salary is $250,000 per year.",
        "The tenant must pay $4,500 monthly rent.",
        "Automatic renewal requires 60 days written notice.",
    ]
    doc_id, user = TestBedStorePayload.seed(vector_service._in_memory_store, texts)
    query = EmbeddingService.generate_embedding(
        "What is the termination notice period?", is_query=True
    )

    numpy_res = vector_service._memory_search(user, query, top_k=3, document_ids={doc_id})
    monkeypatch.setattr(vector_service, "_HAS_NUMPY", False)
    pure_res = vector_service._memory_search(user, query, top_k=3, document_ids={doc_id})

    ids1 = [r["chunk_id"] for r in numpy_res]
    ids2 = [r["chunk_id"] for r in pure_res]
    assert ids1 == ids2
    for a, b in zip(numpy_res, pure_res):
        assert abs(a["score"] - b["score"]) < 1e-9
    # The relevant chunk must rank first on both paths.
    assert "termination" in numpy_res[0]["text"].lower()


def test_memory_search_respects_document_filter(monkeypatch):
    texts_a = ["The termination notice period is 30 days.", "Salary is $250,000."]
    texts_b = ["Monthly rent is $4,500 due on the 1st."]
    TestBedStorePayload.seed(vector_service._in_memory_store, texts_a, doc_id="doc-a")
    for i, t in enumerate(texts_b):
        vec = EmbeddingService.generate_embedding(t, is_query=False)
        vector_service._in_memory_store[f"b-{i}"] = {
            "vector": vec,
            "payload": {
                "chunk_id": f"b-{i}",
                "document_id": "doc-b",
                "document_name": "lease.txt",
                "user_id": "user-x",
                "page_number": 1,
                "section": "General",
                "clause_id": "",
                "text": t,
            },
        }
    query = EmbeddingService.generate_embedding("rent payment", is_query=True)
    query_result = vector_service._memory_search("user-x", query, top_k=5, document_ids={"doc-b"})
    assert all(r["document_id"] == "doc-b" for r in query_result)
    assert any("rent" in r["text"].lower() for r in query_result)


# --- rag_service history de-duplication ----------------------------------------


def test_rag_history_fetched_once_per_ask(monkeypatch):
    """ask_question reads conversation history exactly once (was twice)."""
    store = {"documents": {}, "analyses": {}, "conversations": {}}
    patch_load = patch.object(rag_module, "_load_db", side_effect=lambda: store)
    patch_save = patch.object(rag_module, "_save_db", side_effect=lambda d: store.update(d))
    patch_embed = patch.object(
        rag_module.EmbeddingService, "generate_embedding", return_value=[0.1] * 768
    )
    patch_docs = patch(
        "app.services.document_service.DocumentManager.get_user_documents",
        return_value=[SimpleNamespace(id="doc-A", name="Employment_Contract.pdf")],
    )
    patch_entry = patch(
        "app.services.document_service.DocumentManager.get_document_by_id",
        return_value={"metadata": {"name": "Employment_Contract.pdf", "indexingStatus": "indexed"}},
    )
    patch_key = patch.object(rag_module.settings, "GEMINI_API_KEY", "your_gemini_api_key_here")
    history_mock = Mock(return_value=[])
    patch_hist = patch.object(RAGService, "get_conversation_history", history_mock)
    patch_search = patch.object(
        rag_module.VectorDatabaseService, "search_similar_chunks", return_value=[]
    )
    patch_search_user = patch.object(
        rag_module.VectorDatabaseService, "search_user_chunks", return_value=[]
    )
    patch_filtered = patch.object(
        rag_module.VectorDatabaseService, "search_filtered_chunks", return_value=[]
    )
    patch_general = patch(
        "app.services.ai.general_chat_service.GeneralChatService.ask_pure_general",
        return_value=SimpleNamespace(
            answer="general guidance about notice periods.",
            sources=[],
            confidence="low",
            followup_questions=[],
        ),
    )

    patchers = (
        patch_load,
        patch_save,
        patch_embed,
        patch_docs,
        patch_entry,
        patch_key,
        patch_hist,
        patch_search,
        patch_search_user,
        patch_filtered,
        patch_general,
    )
    for p in patchers:
        p.start()
    try:
        asyncio.run(
            RAGService.ask_question(
                user_id="usr-1",
                document_id="doc-A",
                document_name="Employment_Contract.pdf",
                question="What is the notice period?",
            )
        )
    finally:
        for p in reversed(patchers):
            p.stop()

    assert history_mock.call_count == 1


if __name__ == "__main__":
    unittest.main()

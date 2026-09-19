import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.ai import rag_service as rag_module
from app.services.ai.general_chat_service import GeneralChatService
from app.services.ai.rag_service import RAGService


def _chunk(doc_id, name, text, page=7, section="Termination"):
    return {
        "score": 0.9,
        "chunk_id": f"{doc_id}_chk_0",
        "document_id": doc_id,
        "document_name": name,
        "user_id": "usr-1",
        "page_number": page,
        "section": section,
        "clause_id": "8",
        "text": text,
    }


class TestPhase6Workflow(unittest.TestCase):
    """ChatGPT-style workflow: doc scope, cross-doc fallback, ownership, history."""

    def setUp(self):
        self.store = {"documents": {}, "analyses": {}, "conversations": {}}
        self.user = "usr-workflow-1"

        p_load = patch.object(rag_module, "_load_db", side_effect=lambda: self.store)
        p_save = patch.object(
            rag_module,
            "_save_db",
            side_effect=lambda data: self.store.update(data),
        )
        p_embed = patch.object(
            rag_module.EmbeddingService, "generate_embedding", return_value=[0.1] * 768
        )
        p_docs = patch(
            "app.services.document_service.DocumentManager.get_user_documents",
            return_value=[
                SimpleNamespace(id="doc-A", name="Employment_Contract.pdf"),
                SimpleNamespace(id="doc-B", name="Rental_Agreement.pdf"),
            ],
        )
        p_entry = patch(
            "app.services.document_service.DocumentManager.get_document_by_id",
            return_value={
                "metadata": {"name": "Employment_Contract.pdf", "indexingStatus": "indexed"}
            },
        )
        p_key = patch.object(rag_module.settings, "GEMINI_API_KEY", "your_gemini_api_key_here")

        self._patchers = [p_load, p_save, p_embed, p_docs, p_entry, p_key]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def _ask(self, **kwargs):
        return asyncio.run(RAGService.ask_question(**kwargs))

    # --- MODE A: selected document answers --------------------------------
    def test_01_doc_scoped_answer(self):
        chunk = _chunk(
            "doc-A", "Employment_Contract.pdf", "The termination notice period is 30 days."
        )
        with patch.object(
            rag_module.VectorDatabaseService, "search_similar_chunks", return_value=[chunk]
        ):
            with patch.object(rag_module.VectorDatabaseService, "search_user_chunks") as mock_cross:
                result = self._ask(
                    user_id=self.user,
                    document_id="doc-A",
                    document_name="Employment_Contract.pdf",
                    question="What is the termination notice period?",
                )
                mock_cross.assert_not_called()
        self.assertIn("30 days", result.answer)
        self.assertTrue(all(s.page == 7 for s in result.sources))

    # --- MODE B: cross-document fallback (the critical Chat-2 test) -------
    def test_02_cross_doc_fallback(self):
        chunk = _chunk(
            "doc-A", "Employment_Contract.pdf", "The termination notice period is 30 days."
        )
        with patch.object(
            rag_module.VectorDatabaseService, "search_similar_chunks", return_value=[]
        ):
            with patch.object(
                rag_module.VectorDatabaseService, "search_user_chunks", return_value=[chunk]
            ):
                result = self._ask(
                    user_id=self.user,
                    document_id="doc-B",
                    document_name="Rental_Agreement.pdf",
                    question="What did my employment contract say about termination?",
                )
        self.assertIn("Employment_Contract.pdf", result.answer)
        self.assertEqual(result.sources[0].document_id, "doc-A")
        conv = self.store["conversations"][result.conversation_id]
        self.assertIn("doc-A", conv["referenced_document_ids"])
        self.assertIn("doc-B", conv["referenced_document_ids"])

    # --- No info anywhere: honest, no hallucination -----------------------
    def test_03_no_info_honest(self):
        with patch.object(
            rag_module.VectorDatabaseService, "search_similar_chunks", return_value=[]
        ):
            with patch.object(
                rag_module.VectorDatabaseService, "search_user_chunks", return_value=[]
            ):
                with patch.object(
                    rag_module.VectorDatabaseService, "search_filtered_chunks", return_value=[]
                ):
                    result = self._ask(
                        user_id=self.user,
                        document_id="doc-A",
                        document_name="Employment_Contract.pdf",
                        question="What is a force majeure clause?",
                    )
        # Pivots to general-knowledge guidance instead of dead-ending.
        self.assertIn("general guidance", result.answer)
        self.assertIn("force majeure", result.answer)

    # --- Indexing guard ----------------------------------------------------
    def test_04_processing_doc_not_queried(self):
        with patch(
            "app.services.document_service.DocumentManager.get_document_by_id",
            return_value={"metadata": {"indexingStatus": "indexing"}},
        ):
            with patch.object(
                rag_module.VectorDatabaseService, "search_similar_chunks"
            ) as mock_search:
                result = self._ask(
                    user_id=self.user,
                    document_id="doc-A",
                    document_name="Employment_Contract.pdf",
                    question="Anything?",
                )
                mock_search.assert_not_called()
        self.assertIn("still being processed", result.answer)

    # --- Ownership: hijacking another user's conversation fails ------------
    def test_05_conversation_hijack_rejected(self):
        RAGService._save_message_pair(self.user, "doc-A", "conv-x", "q", "a", [])
        with self.assertRaises(ValueError):
            RAGService._save_message_pair("usr-attacker", "doc-A", "conv-x", "q", "a", [])

    # --- History separation: doc vs library-wide ---------------------------
    def test_06_history_scoping(self):
        RAGService._save_message_pair(self.user, "doc-A", "conv-doc", "q1", "a1", [])
        RAGService._save_message_pair(self.user, None, "conv-gen", "q2", "a2", [])
        doc_hist = RAGService.get_conversation_history(self.user, "doc-A", None)
        self.assertTrue(all(m["content"] in ("q1", "a1") for m in doc_hist))
        lib_hist = RAGService.get_conversation_history(self.user, None, "conv-gen")
        self.assertTrue(any(m["content"] == "q2" for m in lib_hist))
        listed = RAGService.list_user_conversations(self.user)
        ids = {c["conversation_id"] for c in listed}
        self.assertEqual(ids, {"conv-doc", "conv-gen"})

    # --- General chat persists library-wide history -------------------------
    def test_07_general_chat_saves_history(self):
        import app.services.ai.general_chat_service as gc_module

        with patch.object(GeneralChatService, "_retrieve_user_passages", return_value=[]):
            with patch.object(gc_module.settings, "GEMINI_API_KEY", "your_gemini_api_key_here"):
                resp = asyncio.run(
                    GeneralChatService.ask_question("What is a lease?", self.user, "conv-g1")
                )
        self.assertTrue(resp.answer)
        conv = self.store["conversations"]["conv-g1"]
        self.assertIsNone(conv["document_id"])
        self.assertEqual(len(conv["messages"]), 2)

    # --- Routes --------------------------------------------------------------
    def test_08_chat_routes(self):
        from fastapi.testclient import TestClient

        from app.main import app
        from app.utils import security

        app.dependency_overrides[security.get_current_user] = lambda: {"uid": self.user}
        try:
            client = TestClient(app, raise_server_exceptions=False)
            r = client.get("/api/chat/conversations")
            self.assertEqual(r.status_code, 200)
            self.assertIn("conversations", r.json())
            r = client.get("/api/chat/history")
            self.assertEqual(r.status_code, 200)
        finally:
            app.dependency_overrides.clear()


class TestScopeDetection(unittest.TestCase):
    """Natural-language document reference resolution."""

    def setUp(self):
        self.library = {
            "doc-A": "Employment_Contract.pdf",
            "doc-B": "Rental_Agreement.pdf",
        }

    def _detect(self, q, selected=None):
        return RAGService._detect_referenced_docs(q, self.library, selected)

    def test_specific_named_doc_routes_to_it(self):
        scope = self._detect("What did my employment contract say about termination?", "doc-B")
        self.assertEqual(scope["mode"], "single_referenced")
        self.assertEqual(scope["doc_ids"], ["doc-A"])
        self.assertFalse(scope["ambiguous"])

    def test_generic_reference_ambiguous_when_multiple_docs(self):
        scope = self._detect("What does my contract say?", "doc-A")
        self.assertEqual(scope["mode"], "ambiguous")
        self.assertTrue(scope["ambiguous"])
        self.assertEqual(set(scope["doc_ids"]), {"doc-A", "doc-B"})

    def test_cross_signal_question_routes_to_all(self):
        scope = self._detect("Which of my documents mention automatic renewal?", "doc-A")
        self.assertEqual(scope["mode"], "all")
        self.assertEqual(set(scope["doc_ids"]), {"doc-A", "doc-B"})
        self.assertFalse(scope["ambiguous"])

    def test_compare_routes_to_multi(self):
        scope = self._detect("Compare my employment contract with rental agreement.", "doc-A")
        self.assertEqual(scope["mode"], "multi")
        self.assertEqual(set(scope["doc_ids"]), {"doc-A", "doc-B"})

    def test_distinctive_term_routes_to_single_doc(self):
        scope = self._detect("What does my rental agreement say about pets?", "doc-A")
        self.assertEqual(scope["mode"], "single_referenced")
        self.assertEqual(scope["doc_ids"], ["doc-B"])

    def test_no_reference_uses_selected_doc(self):
        scope = self._detect("What is the notice period?", "doc-A")
        self.assertEqual(scope["mode"], "specific")
        self.assertEqual(scope["doc_ids"], ["doc-A"])


class TestCrossDocIntegrity(unittest.TestCase):
    """Citations + retrieval spanning multiple documents must stay attributed."""

    def setUp(self):
        self.store = {"documents": {}, "analyses": {}, "conversations": {}}
        self.user = "usr-integrity-1"
        p_load = patch.object(rag_module, "_load_db", side_effect=lambda: self.store)
        p_save = patch.object(
            rag_module, "_save_db", side_effect=lambda data: self.store.update(data)
        )
        p_embed = patch.object(
            rag_module.EmbeddingService, "generate_embedding", return_value=[0.1] * 768
        )
        p_docs = patch(
            "app.services.document_service.DocumentManager.get_user_documents",
            return_value=[
                SimpleNamespace(id="doc-A", name="Employment_Contract.pdf"),
                SimpleNamespace(id="doc-B", name="Rental_Agreement.pdf"),
            ],
        )
        p_entry = patch(
            "app.services.document_service.DocumentManager.get_document_by_id",
            return_value={
                "metadata": {"name": "Rental_Agreement.pdf", "indexingStatus": "indexed"}
            },
        )
        p_key = patch.object(rag_module.settings, "GEMINI_API_KEY", "your_gemini_api_key_here")
        self._patchers = [p_load, p_save, p_embed, p_docs, p_entry, p_key]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def test_attribute_sources_same_page_multi_doc(self):
        from app.services.ai.rag_service import SourceCitation

        chunks = [
            _chunk("doc-A", "Employment_Contract.pdf", "text A"),
            _chunk("doc-B", "Rental_Agreement.pdf", "text B"),
        ]
        # Citations that already carry a document_id must keep their own document
        # even when a different doc is on the same page; doc-less citations fall
        # back to the first chunk on that page.
        srcs = [
            SourceCitation(page=7, section="Termination", snippet="s", document_id="doc-B"),
            SourceCitation(page=7, section="Termination", snippet="s"),
        ]
        enriched = RAGService._attribute_sources(srcs, chunks, self.user)
        by_id = {s.document_id: s for s in enriched}
        self.assertIn("doc-B", by_id)
        self.assertEqual(by_id["doc-B"].document_name, "Rental_Agreement.pdf")
        self.assertIn("doc-A", by_id)

    def test_cross_doc_answer_attributes_both_documents(self):
        chunks = [
            _chunk("doc-A", "Employment_Contract.pdf", "Employment termination 30 days"),
            _chunk("doc-B", "Rental_Agreement.pdf", "Rental termination 60 days"),
        ]
        with patch.object(
            rag_module.VectorDatabaseService, "search_filtered_chunks", return_value=chunks
        ):
            with patch.object(
                rag_module.VectorDatabaseService, "search_similar_chunks", return_value=[]
            ):
                with patch.object(
                    rag_module.VectorDatabaseService, "search_user_chunks", return_value=[]
                ):
                    result = asyncio.run(
                        RAGService.ask_question(
                            user_id=self.user,
                            document_id="doc-B",
                            document_name="Rental_Agreement.pdf",
                            question="Compare the termination clauses in my two contracts.",
                        )
                    )
        docs = {s.document_id for s in result.sources if s.document_id}
        self.assertEqual(docs, {"doc-A", "doc-B"})

    def test_unified_ambiguous_reference_asks_clarification(self):
        result = asyncio.run(
            RAGService.ask_unified(
                user_id=self.user, question="What does my contract say?", selected_document_id=None
            )
        )
        self.assertIn("Which document do you mean", result.answer)
        self.assertEqual(result.sources, [])

    def test_unified_library_wide_retrieval(self):
        chunks = [
            _chunk("doc-A", "Employment_Contract.pdf", "Employment termination 30 days"),
            _chunk("doc-B", "Rental_Agreement.pdf", "Rental termination 60 days"),
        ]
        with patch.object(
            rag_module.VectorDatabaseService, "search_filtered_chunks", return_value=chunks
        ):
            with patch.object(
                rag_module.VectorDatabaseService, "search_similar_chunks", return_value=[]
            ):
                with patch.object(
                    rag_module.VectorDatabaseService, "search_user_chunks", return_value=[]
                ):
                    result = asyncio.run(
                        RAGService.ask_unified(
                            user_id=self.user,
                            question="Which of my documents mention automatic renewal?",
                            selected_document_id=None,
                        )
                    )
        self.assertTrue(result.answer)
        docs = {s.document_id for s in result.sources if s.document_id}
        self.assertEqual(docs, {"doc-A", "doc-B"})
        conv = self.store["conversations"][result.conversation_id]
        self.assertIsNone(conv["document_id"])
        self.assertEqual(set(conv["referenced_document_ids"]), {"doc-A", "doc-B"})


if __name__ == "__main__":
    unittest.main()

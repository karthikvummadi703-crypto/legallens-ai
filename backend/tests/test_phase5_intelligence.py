import asyncio
import os
import unittest
from unittest.mock import patch

from app.services.ai.comparison_service import ComparisonService
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.gemini_service import GeminiAnalysisService
from app.services.ai.schemas import DocumentComparison
from app.services.ai.vector_service import VectorDatabaseService
from app.services.document_service import DocumentManager
from app.services.extraction_service import DocumentExtractionService


def _write_sample(path, body):
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


class TestPhase5Intelligence(unittest.TestCase):
    def setUp(self):
        self.test_user_id = "test-usr-phase5"
        self.dir = os.path.dirname(__file__)
        self.doc_a_path = os.path.join(self.dir, "sample_compare_a.txt")
        self.doc_b_path = os.path.join(self.dir, "sample_compare_b.txt")
        _write_sample(
            self.doc_a_path,
            "--- Page 1 ---\n"
            "CONSULTING AGREEMENT\n"
            "This Consulting Agreement is entered into by Client and Consultant.\n\n"
            "SECTION 1: SERVICES\n"
            "Consultant shall deliver monthly progress reports.\n\n"
            "SECTION 2: COMPENSATION\n"
            "Base fee shall be $5,000 per month, payable within 30 days of invoice.\n\n"
            "SECTION 3: TERMINATION\n"
            "Either party may terminate with 30 days written notice.\n",
        )
        _write_sample(
            self.doc_b_path,
            "--- Page 1 ---\n"
            "CONSULTING AGREEMENT (REVISED)\n"
            "This Consulting Agreement is entered into by Client and Consultant.\n\n"
            "SECTION 1: SERVICES\n"
            "Consultant shall deliver weekly progress reports.\n\n"
            "SECTION 2: COMPENSATION\n"
            "Base fee shall be $6,000 per month, payable within 15 days of invoice.\n\n"
            "SECTION 3: TERMINATION\n"
            "Either party may terminate with 60 days written notice.\n\n"
            "SECTION 4: CONFIDENTIALITY\n"
            "Consultant shall keep all client materials strictly confidential.\n",
        )

    def tearDown(self):
        for p in (self.doc_a_path, self.doc_b_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        try:
            VectorDatabaseService.delete_user_vectors(self.test_user_id)
        except Exception:
            pass

    def _entry(self, path, doc_id, name):
        extracted = DocumentExtractionService.extract_document(path, doc_id, name)
        return {"metadata": {"name": name}, "extracted": extracted.model_dump()}

    # --- Comparison: honest deterministic fallback -------------------
    def test_01_compare_fallback_is_grounded(self):
        entry_a = self._entry(self.doc_a_path, "doc-a", "consulting_agreement.txt")
        entry_b = self._entry(self.doc_b_path, "doc-b", "consulting_agreement_revised.txt")
        result = ComparisonService._grounded_fallback_compare(
            "doc-a",
            "Consulting Agreement",
            entry_a,
            None,
            "doc-b",
            "Consulting Agreement (Revised)",
            entry_b,
            None,
        )
        self.assertIsInstance(result, DocumentComparison)
        self.assertEqual(result.document_a_id, "doc-a")
        self.assertEqual(result.document_b_id, "doc-b")
        self.assertGreater(len(result.differences), 0)
        # Every difference must reference a real side, never invented text.
        for d in result.differences:
            self.assertIn(d.difference_type, ("Added", "Removed", "Changed", "Unchanged"))
            self.assertTrue(d.contract_a or d.contract_b)
        counted = [
            d for d in result.differences if d.difference_type in ("Added", "Removed", "Changed")
        ]
        self.assertEqual(result.summary.total_changed, len(counted))
        self.assertIn("informational assistance", result.disclaimer)

    def test_02_compare_same_document_rejected(self):
        with self.assertRaises(ValueError):
            asyncio.run(
                ComparisonService.compare_documents(self.test_user_id, "doc-same", "doc-same")
            )

    def test_03_compare_unknown_document_rejected(self):
        # Read-only against the real DB; raises without writing anything.
        with self.assertRaises(ValueError):
            asyncio.run(
                ComparisonService.compare_documents(
                    self.test_user_id, "doc-missing-1", "doc-missing-2"
                )
            )

    # --- Checklist: built from real analysis, empty without it -------
    def test_04_checklist_from_real_analysis(self):
        extracted = DocumentExtractionService.extract_document(
            self.doc_a_path, "doc-chk", "consulting_agreement.txt"
        )
        analysis = GeminiAnalysisService._generate_grounded_fallback_analysis(
            extracted, self.test_user_id
        )
        with patch.object(DocumentManager, "get_document_analysis", return_value=analysis):
            items = DocumentManager.get_document_checklist("doc-chk", self.test_user_id)
        self.assertGreater(len(items), 0)
        allowed_sections = {
            "Payments",
            "Term",
            "Termination",
            "Obligations",
            "Liability",
            "Dispute Resolution",
            "General",
        }
        for item in items:
            self.assertIn(item.section, allowed_sections)
            self.assertTrue(item.title)
            self.assertFalse(item.completed)
        # Payment and obligation findings must mention the real figures/duties.
        joined = " ".join(i.title + " " + i.explanation for i in items)
        self.assertIn("$5,000", joined)
        self.assertIn("progress reports", joined)

    def test_05_checklist_empty_without_analysis(self):
        with patch.object(DocumentManager, "get_document_analysis", return_value=None):
            items = DocumentManager.get_document_checklist("doc-none", self.test_user_id)
        self.assertEqual(items, [])

    # --- Cross-document vector search --------------------------------
    def test_06_cross_doc_search_spans_documents(self):
        chunks_a = [
            {
                "chunk_id": "phase5-a_chk_0",
                "document_id": "doc-a",
                "page_number": 1,
                "section": "Compensation",
                "clause_id": "",
                "chunk_index": 0,
                "text": "Base fee shall be $5,000 per month.",
            }
        ]
        chunks_b = [
            {
                "chunk_id": "phase5-b_chk_0",
                "document_id": "doc-b",
                "page_number": 1,
                "section": "Compensation",
                "clause_id": "",
                "chunk_index": 0,
                "text": "Base fee shall be $6,000 per month.",
            }
        ]
        vec_a = EmbeddingService.generate_embedding(chunks_a[0]["text"])
        vec_b = EmbeddingService.generate_embedding(chunks_b[0]["text"])
        self.assertTrue(
            VectorDatabaseService.upsert_document_chunks(
                self.test_user_id, "doc-a", chunks_a, [vec_a], document_name="Agreement A"
            )
        )
        self.assertTrue(
            VectorDatabaseService.upsert_document_chunks(
                self.test_user_id, "doc-b", chunks_b, [vec_b], document_name="Agreement B"
            )
        )

        query = EmbeddingService.generate_embedding("What is the monthly base fee?")
        results = VectorDatabaseService.search_user_chunks(self.test_user_id, query, top_k=5)
        doc_ids = {r["document_id"] for r in results}
        # Both documents surface through the user-wide (document-unrestricted) search.
        self.assertIn("doc-a", doc_ids)
        self.assertIn("doc-b", doc_ids)
        names = {r["document_name"] for r in results}
        self.assertIn("Agreement A", names)
        self.assertIn("Agreement B", names)

    # --- Route wiring (auth stubbed, no Firebase needed) -------------
    def test_07_routes_registered(self):
        from fastapi.testclient import TestClient

        from app.main import app
        from app.utils import security

        app.dependency_overrides[security.get_current_user] = lambda: {"uid": self.test_user_id}
        try:
            client = TestClient(app, raise_server_exceptions=False)
            r = client.post(
                "/api/documents/compare",
                json={"document_a_id": "doc-missing-1", "document_b_id": "doc-missing-2"},
            )
            self.assertEqual(r.status_code, 404)
            r = client.get("/api/documents/doc-missing-1/checklist")
            self.assertEqual(r.status_code, 404)
            r = client.post(
                "/api/documents/compare",
                json={"document_a_id": "doc-same", "document_b_id": "doc-same"},
            )
            self.assertEqual(r.status_code, 404)
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()

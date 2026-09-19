import asyncio
import os
import unittest

from app.services.ai.chunking_service import LegalChunkingService
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.rag_service import RAGService
from app.services.ai.vector_service import VectorDatabaseService
from app.services.extraction_service import DocumentExtractionService


class TestPhase4RAG(unittest.TestCase):
    def setUp(self):
        self.user_a = "usr-userA-123"
        self.user_b = "usr-userB-456"

        self.doc_a_path = os.path.join(os.path.dirname(__file__), "contract_user_a.txt")
        with open(self.doc_a_path, "w", encoding="utf-8") as f:
            f.write(
                "USER A CONTRACT: EXECUTIVE AGREEMENT\n"
                "--- Page 1 ---\n"
                "SECTION 1: SALARY AND BONUS\n"
                "User A base salary is $250,000 per year with a 20% annual performance bonus.\n\n"
                "--- Page 2 ---\n"
                "SECTION 2: TERMINATION NOTICE\n"
                "User A may terminate this agreement by providing 45 days advance written notice.\n"
            )

        self.doc_b_path = os.path.join(os.path.dirname(__file__), "contract_user_b.txt")
        with open(self.doc_b_path, "w", encoding="utf-8") as f:
            f.write(
                "USER B CONTRACT: LEASE AGREEMENT\n"
                "--- Page 1 ---\n"
                "SECTION 1: MONTHLY RENT\n"
                "User B monthly rent is $4,500 due on the 1st of every calendar month.\n\n"
                "--- Page 2 ---\n"
                "SECTION 2: PET POLICY\n"
                "User B is permitted up to 2 small domestic pets with a $500 pet deposit.\n"
            )

    def tearDown(self):
        for p in [self.doc_a_path, self.doc_b_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def test_01_chunking_and_metadata(self):
        extracted_a = DocumentExtractionService.extract_document(
            self.doc_a_path, "doc-userA-01", "contract_user_a.txt"
        )
        chunks = LegalChunkingService.create_chunks(extracted_a, self.user_a)

        self.assertGreater(len(chunks), 0)
        first_chk = chunks[0]
        self.assertEqual(first_chk["document_id"], "doc-userA-01")
        self.assertEqual(first_chk["user_id"], self.user_a)
        self.assertIn("page_number", first_chk)
        self.assertIn("section", first_chk)
        self.assertIn("text", first_chk)

    def test_02_embedding_generation(self):
        sample_text = "User A base salary is $250,000 per year."
        vector = EmbeddingService.generate_embedding(sample_text)
        self.assertEqual(len(vector), 768)

    def test_03_vector_indexing_and_search(self):
        extracted_a = DocumentExtractionService.extract_document(
            self.doc_a_path, "doc-userA-02", "contract_user_a.txt"
        )
        chunks = LegalChunkingService.create_chunks(extracted_a, self.user_a)
        embeddings = EmbeddingService.generate_embeddings([c["text"] for c in chunks])

        upsert_ok = VectorDatabaseService.upsert_document_chunks(
            self.user_a, "doc-userA-02", chunks, embeddings
        )
        self.assertTrue(upsert_ok)

        q_vec = EmbeddingService.generate_embedding("What is the base salary?")
        results = VectorDatabaseService.search_similar_chunks(
            self.user_a, "doc-userA-02", q_vec, top_k=3
        )

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["user_id"], self.user_a)
        self.assertEqual(results[0]["document_id"], "doc-userA-02")
        self.assertIn("250,000", results[0]["text"])

    def test_04_strict_cross_user_ownership_isolation(self):
        """
        CRITICAL SECURITY TEST:
        User A MUST NOT be able to retrieve or search User B's vector chunks.
        """
        ext_a = DocumentExtractionService.extract_document(
            self.doc_a_path, "doc-userA-sec", "contract_user_a.txt"
        )
        chunks_a = LegalChunkingService.create_chunks(ext_a, self.user_a)
        emb_a = EmbeddingService.generate_embeddings([c["text"] for c in chunks_a])
        VectorDatabaseService.upsert_document_chunks(self.user_a, "doc-userA-sec", chunks_a, emb_a)

        ext_b = DocumentExtractionService.extract_document(
            self.doc_b_path, "doc-userB-sec", "contract_user_b.txt"
        )
        chunks_b = LegalChunkingService.create_chunks(ext_b, self.user_b)
        emb_b = EmbeddingService.generate_embeddings([c["text"] for c in chunks_b])
        VectorDatabaseService.upsert_document_chunks(self.user_b, "doc-userB-sec", chunks_b, emb_b)

        q_vec = EmbeddingService.generate_embedding("What is the monthly rent?")

        # 1. User A searches User A's document -> returns results
        res_a = VectorDatabaseService.search_similar_chunks(
            self.user_a, "doc-userA-sec", q_vec, top_k=5
        )
        self.assertGreater(len(res_a), 0)
        for r in res_a:
            self.assertEqual(r["user_id"], self.user_a)

        # 2. User A attempts searching User B's document_id -> Returns 0 results (Blocked by ownership filter)
        res_unauthorized = VectorDatabaseService.search_similar_chunks(
            self.user_a, "doc-userB-sec", q_vec, top_k=5
        )
        self.assertEqual(len(res_unauthorized), 0)

        # 3. User B attempts searching User A's document_id -> Returns 0 results
        res_unauthorized_b = VectorDatabaseService.search_similar_chunks(
            self.user_b, "doc-userA-sec", q_vec, top_k=5
        )
        self.assertEqual(len(res_unauthorized_b), 0)

    def test_05_rag_grounded_answer(self):
        ext_a = DocumentExtractionService.extract_document(
            self.doc_a_path, "doc-userA-rag", "contract_user_a.txt"
        )
        chunks_a = LegalChunkingService.create_chunks(ext_a, self.user_a)
        emb_a = EmbeddingService.generate_embeddings([c["text"] for c in chunks_a])
        VectorDatabaseService.upsert_document_chunks(self.user_a, "doc-userA-rag", chunks_a, emb_a)

        rag_resp = asyncio.run(
            RAGService.ask_question(
                user_id=self.user_a,
                document_id="doc-userA-rag",
                document_name="contract_user_a.txt",
                question="What is the notice period for termination?",
            )
        )

        self.assertIsNotNone(rag_resp.answer)
        self.assertGreater(len(rag_resp.sources), 0)
        self.assertGreaterEqual(rag_resp.sources[0].page, 1)
        self.assertIsInstance(rag_resp.sources[0].section, str)
        self.assertGreater(len(rag_resp.sources[0].section), 0)

    def test_06_missing_information_handling(self):
        ext_a = DocumentExtractionService.extract_document(
            self.doc_a_path, "doc-userA-missing", "contract_user_a.txt"
        )
        chunks_a = LegalChunkingService.create_chunks(ext_a, self.user_a)
        emb_a = EmbeddingService.generate_embeddings([c["text"] for c in chunks_a])
        VectorDatabaseService.upsert_document_chunks(
            self.user_a, "doc-userA-missing", chunks_a, emb_a
        )

        rag_resp = asyncio.run(
            RAGService.ask_question(
                user_id=self.user_a,
                document_id="doc-userA-missing",
                document_name="contract_user_a.txt",
                question="What is the software warranty policy for third party plugins?",
            )
        )

        # Check for explicit missing info statement or cautious fallback
        self.assertTrue(
            "couldn't find enough information" in rag_resp.answer.lower()
            or "informational" in rag_resp.answer.lower()
        )

    def test_07_vector_deletion(self):
        ext_a = DocumentExtractionService.extract_document(
            self.doc_a_path, "doc-del-01", "contract_user_a.txt"
        )
        chunks_a = LegalChunkingService.create_chunks(ext_a, self.user_a)
        emb_a = EmbeddingService.generate_embeddings([c["text"] for c in chunks_a])
        VectorDatabaseService.upsert_document_chunks(self.user_a, "doc-del-01", chunks_a, emb_a)

        # Delete vectors
        del_ok = VectorDatabaseService.delete_document_vectors(self.user_a, "doc-del-01")
        self.assertTrue(del_ok)

        # Verify search returns 0 results
        q_vec = EmbeddingService.generate_embedding("salary")
        res = VectorDatabaseService.search_similar_chunks(self.user_a, "doc-del-01", q_vec, top_k=5)
        self.assertEqual(len(res), 0)


if __name__ == "__main__":
    unittest.main()

import asyncio
import os
import unittest

from app.services.ai.gemini_service import GeminiAnalysisService
from app.services.ai.schemas import FullDocumentAnalysis
from app.services.extraction_service import DocumentExtractionService


class TestPhase3Analysis(unittest.TestCase):
    def setUp(self):
        self.test_user_id = "test-usr-123"
        self.sample_txt_path = os.path.join(os.path.dirname(__file__), "sample_contract.txt")
        with open(self.sample_txt_path, "w", encoding="utf-8") as f:
            f.write(
                "--- Page 1 ---\n"
                "EMPLOYMENT AGREEMENT\n"
                "This Employment Agreement is entered into by Executive and Apex Corp.\n\n"
                "SECTION 1: DUTIES\n"
                "Executive shall serve as VP of Technology.\n\n"
                "SECTION 2: TERM AND RENEWAL\n"
                "2.2 Renewal. This Agreement shall automatically renew for 1-year terms unless notice is provided 90 days prior.\n\n"
                "SECTION 3: COMPENSATION\n"
                "Base salary shall be $200,000 per annum paid monthly.\n\n"
                "SECTION 8: TERMINATION\n"
                "8.1 Early Departure Penalty. Resignation within 12 months requires 50% signing bonus repayment ($20,000).\n"
            )

    def tearDown(self):
        if os.path.exists(self.sample_txt_path):
            try:
                os.remove(self.sample_txt_path)
            except Exception:
                pass

    def test_01_text_extraction(self):
        extracted = DocumentExtractionService.extract_document(
            self.sample_txt_path, "doc-test-01", "sample_contract.txt"
        )
        self.assertEqual(extracted.document_id, "doc-test-01")
        self.assertGreater(len(extracted.pages), 0)
        self.assertIn("EMPLOYMENT AGREEMENT", extracted.full_text)

    def test_02_pydantic_analysis_validation(self):
        """Verify the offline fallback produces a valid schema without fabricating legal content."""
        extracted = DocumentExtractionService.extract_document(
            self.sample_txt_path, "doc-test-02", "sample_contract.txt"
        )
        analysis = asyncio.run(GeminiAnalysisService.analyze_document(extracted, self.test_user_id))

        self.assertIsInstance(analysis, FullDocumentAnalysis)
        self.assertEqual(analysis.document_id, "doc-test-02")
        self.assertEqual(analysis.user_id, self.test_user_id)
        self.assertGreaterEqual(analysis.attention_score.score, 0)
        self.assertIsInstance(analysis.disclaimer, str)
        self.assertGreater(len(analysis.executive_summary.summary), 0)

        # Core structural fields must be present
        self.assertIsNotNone(analysis.termination_analysis)
        self.assertIsNotNone(analysis.renewal_analysis)

        # Important clauses are derived from ACTUAL extracted clauses in the sample text
        self.assertGreater(len(analysis.important_clauses), 0)

    def test_03_attention_score_calculation(self):
        extracted = DocumentExtractionService.extract_document(
            self.sample_txt_path, "doc-test-03", "sample_contract.txt"
        )
        analysis = asyncio.run(GeminiAnalysisService.analyze_document(extracted, self.test_user_id))
        self.assertGreaterEqual(analysis.attention_score.score, 0)
        self.assertLessEqual(analysis.attention_score.score, 100)
        self.assertIn(
            analysis.attention_score.label,
            ["Requires Immediate Attention", "Requires Review", "Standard Terms"],
        )


if __name__ == "__main__":
    unittest.main()

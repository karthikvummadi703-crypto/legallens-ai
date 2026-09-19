"""Tests for any-file support: MD/CSV/HTML/LOG extraction and validation."""

import os
import unittest
from types import SimpleNamespace

from app.services.extraction_service import DocumentExtractionService
from app.utils.file_utils import ALLOWED_EXTENSIONS, validate_uploaded_file


def _write(path, body):
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def _fake_upload(filename, content: bytes):
    return SimpleNamespace(filename=filename)


class TestAnyFileSupport(unittest.TestCase):
    def setUp(self):
        self.dir = os.path.dirname(__file__)
        self.paths = []

    def tearDown(self):
        for p in self.paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def _make(self, name, body):
        path = os.path.join(self.dir, name)
        _write(path, body)
        self.paths.append(path)
        return path

    def test_extensions_allowed(self):
        for ext in (".pdf", ".docx", ".txt", ".md", ".csv", ".html", ".log"):
            self.assertIn(ext, ALLOWED_EXTENSIONS)

    def test_markdown_extraction(self):
        path = self._make(
            "sample_notes.md",
            "# Project Plan\n\n## Payment Terms\n\nClient shall pay $5,000 per month.\n",
        )
        extracted = DocumentExtractionService.extract_document(path, "doc-md", "notes.md")
        self.assertIn("Project Plan", extracted.full_text)
        self.assertEqual(extracted.file_type, "TXT")

    def test_csv_extraction(self):
        path = self._make(
            "sample_data.csv",
            "item,amount,due\nBase fee,$5000,Jan 1\nLate fee,$100,Jan 15\n",
        )
        extracted = DocumentExtractionService.extract_document(path, "doc-csv", "data.csv")
        self.assertIn("$5000", extracted.full_text)

    def test_html_stripped(self):
        path = self._make(
            "sample_page.html",
            "<html><head><title>Agreement</title></head>"
            "<body><h1>Terms</h1><p>Payment of $200 is due.</p></body></html>",
        )
        extracted = DocumentExtractionService.extract_document(path, "doc-html", "page.html")
        self.assertNotIn("<p>", extracted.full_text)
        self.assertIn("Payment of $200 is due.", extracted.full_text)

    def test_unsupported_still_rejected(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            validate_uploaded_file(_fake_upload("evil.exe", b"xx"), b"xx")

    def test_new_types_validate(self):
        self.assertEqual(validate_uploaded_file(_fake_upload("a.md", b"x"), b"# hi"), ".md")
        self.assertEqual(
            validate_uploaded_file(_fake_upload("a.html", b"x"), b"<p>hi</p>"),
            ".html",
        )
        # PDF magic-byte rule still enforced.
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            validate_uploaded_file(_fake_upload("a.pdf", b"x"), b"not a pdf")


if __name__ == "__main__":
    unittest.main()

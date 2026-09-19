import os
import re
from typing import List, Tuple
from app.models.document import ExtractedDocument, PageContent, DocumentSection, DocumentClause
from app.core.logging import logger


class DocumentExtractionService:
    """
    Phase 2 (Optimised): Page-Aware Legal Text Extraction Engine.
    Handles PDF (PyMuPDF), DOCX (python-docx), and plain-text formats
    (TXT, MD, CSV, HTML, LOG). Any readable document — legal or otherwise —
    is extracted, chunked and made analyzable.

    Optimisations over the original implementation:
    - Table extraction via PyMuPDF find_tables() for payment schedules etc.
    - Comprehensive clause detection (numbered, lettered, Roman, Article/Clause)
    - Full clause body text capture instead of title-only
    - Better section detection (bold headings, markdown headers, underlined)
    - Improved handling of scanned/empty pages
    """

    # Extensions handled by the plain-text reader.
    TEXT_LIKE_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".log"}

    # ------------------------------------------------------------------ #
    # Clause detection patterns (priority-ordered)
    # ------------------------------------------------------------------ #
    # 1. Numbered: "1. Title", "1.2 Title", "1.2.3 Title"
    # 2. Article/Section prefix: "Article 5 — Title", "Section 3. Title", "Clause 4: Title"
    # 3. Lettered: "(a) Title", "(b) Title"
    # 4. Roman numerals: "IV. Title", "III Title"
    _CLAUSE_PATTERNS = [
        # Numbered clauses: 1. / 1.2 / 1.2.3 followed by a title word
        re.compile(
            r'^(\d{1,3}(?:\.\d{1,3}){0,4})[\.\)]\s+([A-Z][^\n]{3,80})',
            re.MULTILINE,
        ),
        # Article / Section / Clause prefix
        re.compile(
            r'^((?:Article|Section|Clause|Part|Schedule|Appendix|Annex|Exhibit)\s+'
            r'(?:\d{1,3}(?:\.\d{1,3}){0,2}|[IVXLCDM]+|[A-Z]))'
            r'[\s\.\:\—\-–]+([A-Z][^\n]{3,80})',
            re.MULTILINE | re.IGNORECASE,
        ),
        # Lettered clauses: (a) / (b) / (i) / (ii)
        re.compile(
            r'^\(([a-z]{1,4}|[ivxlcdm]{1,6})\)\s+([A-Z][^\n]{3,80})',
            re.MULTILINE,
        ),
        # Roman numeral clauses: IV. Title
        re.compile(
            r'^([IVXLCDM]{1,6})[\.\)]\s+([A-Z][^\n]{3,80})',
            re.MULTILINE,
        ),
    ]

    # ------------------------------------------------------------------ #
    # Section detection patterns (for structural headings)
    # ------------------------------------------------------------------ #
    _SECTION_PATTERNS = [
        # Numbered section headers: "1. DEFINITIONS", "SECTION 5 — PAYMENT"
        re.compile(
            r'^(?:(?:SECTION|ARTICLE|PART|SCHEDULE)\s+)?'
            r'(?:\d{1,3}[\.\)]?\s+)?'
            r'([A-Z][A-Z\s\-&,]{3,50})\s*$',
            re.MULTILINE,
        ),
        # Markdown-style headers: "# Title", "## Title"
        re.compile(r'^#{1,4}\s+(.{3,60})\s*$', re.MULTILINE),
        # Underlined headers (line followed by === or ---)
        re.compile(r'^(.{3,60})\n[=\-]{3,}\s*$', re.MULTILINE),
    ]

    @classmethod
    def extract_document(cls, file_path: str, document_id: str, original_filename: str) -> ExtractedDocument:
        ext = os.path.splitext(original_filename)[1].lower()
        file_size = os.path.getsize(file_path)

        if ext == ".pdf":
            pages = cls._extract_pdf(file_path)
        elif ext == ".docx":
            pages = cls._extract_docx(file_path)
        elif ext in cls.TEXT_LIKE_EXTENSIONS:
            pages = cls._extract_txt(file_path)
            if ext in (".html", ".htm"):
                pages = cls._strip_html_pages(pages)
        else:
            raise ValueError(f"Unsupported extension {ext}")

        full_text = "\n\n".join([f"--- Page {p.page_number} ---\n{p.text}" for p in pages])
        sections = cls._detect_sections(pages)
        clauses = cls._detect_clauses_full(pages, sections)

        # Normalise text-like formats to TXT so existing clients keep working.
        file_type = ext.replace(".", "").upper()
        if ext in cls.TEXT_LIKE_EXTENSIONS and ext != ".txt":
            file_type = "TXT"

        return ExtractedDocument(
            document_id=document_id,
            filename=original_filename,
            file_type=file_type,
            file_size=file_size,
            total_pages=len(pages),
            pages=pages,
            sections=sections,
            clauses=clauses,
            full_text=full_text
        )

    # ================================================================== #
    # PDF extraction (with table support)
    # ================================================================== #
    @classmethod
    def _extract_pdf(cls, file_path: str) -> List[PageContent]:
        pages = []
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            for i, page in enumerate(doc):
                text = page.get_text("text").strip()

                # If text extraction yields very little, try blocks mode
                if len(text) < 50:
                    blocks = page.get_text("blocks")
                    block_texts = [
                        b[4].strip() for b in blocks
                        if isinstance(b[4], str) and b[4].strip()
                    ]
                    if block_texts:
                        text = "\n".join(block_texts)

                # Extract tables and append as structured text
                table_text = cls._extract_page_tables(page)
                if table_text:
                    text = text + "\n\n" + table_text if text else table_text

                if not text or len(text) < 10:
                    text = (
                        f"[Page {i + 1}: This page appears to contain scanned content or images. "
                        "Text extraction was limited. Consider re-uploading a text-based PDF for best results.]"
                    )

                pages.append(PageContent(
                    page_number=i + 1,
                    text=text,
                    character_count=len(text)
                ))
            doc.close()
        except Exception as e:
            logger.error(f"PyMuPDF PDF extraction error: {e}")
            pages.append(PageContent(page_number=1, text="Error reading PDF pages", character_count=24))
        return pages if pages else [PageContent(page_number=1, text="Empty document", character_count=14)]

    @classmethod
    def _extract_page_tables(cls, page) -> str:
        """Extract tables from a PDF page using PyMuPDF's find_tables()."""
        try:
            tables = page.find_tables()
            if not tables or not tables.tables:
                return ""

            table_blocks = []
            for table in tables.tables:
                try:
                    rows = table.extract()
                    if not rows:
                        continue
                    # Format as a readable text table
                    formatted_rows = []
                    for row in rows:
                        cells = [str(cell).strip() if cell else "" for cell in row]
                        if any(cells):  # Skip fully empty rows
                            formatted_rows.append(" | ".join(cells))
                    if formatted_rows:
                        table_blocks.append(
                            "[TABLE]\n" + "\n".join(formatted_rows) + "\n[/TABLE]"
                        )
                except Exception:
                    continue
            return "\n\n".join(table_blocks)
        except AttributeError:
            # find_tables() not available in this PyMuPDF version
            return ""
        except Exception as e:
            logger.debug(f"Table extraction skipped for page ({e})")
            return ""

    # ================================================================== #
    # DOCX extraction
    # ================================================================== #
    @classmethod
    def _extract_docx(cls, file_path: str) -> List[PageContent]:
        pages = []
        try:
            import docx
            doc = docx.Document(file_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

            # Also extract tables from DOCX
            for table in doc.tables:
                table_rows = []
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        table_rows.append(" | ".join(cells))
                if table_rows:
                    paragraphs.append("[TABLE]\n" + "\n".join(table_rows) + "\n[/TABLE]")

            # Group into synthetic ~3000 character pages to preserve pagination contract
            page_text = []
            current_len = 0
            page_num = 1

            for p in paragraphs:
                page_text.append(p)
                current_len += len(p)
                if current_len >= 2500:
                    text_str = "\n\n".join(page_text)
                    pages.append(PageContent(page_number=page_num, text=text_str, character_count=len(text_str)))
                    page_num += 1
                    page_text = []
                    current_len = 0

            if page_text:
                text_str = "\n\n".join(page_text)
                pages.append(PageContent(page_number=page_num, text=text_str, character_count=len(text_str)))
        except Exception as e:
            logger.error(f"python-docx extraction error: {e}")
            pages.append(PageContent(page_number=1, text="Error extracting DOCX text", character_count=26))
        return pages if pages else [PageContent(page_number=1, text="Empty DOCX document", character_count=19)]

    # ================================================================== #
    # Plain text extraction
    # ================================================================== #
    @classmethod
    def _extract_txt(cls, file_path: str) -> List[PageContent]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                raw_text = f.read()

        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        pages = []
        page_text = []
        current_len = 0
        page_num = 1

        for p in paragraphs:
            page_text.append(p)
            current_len += len(p)
            if current_len >= 2500:
                text_str = "\n\n".join(page_text)
                pages.append(PageContent(page_number=page_num, text=text_str, character_count=len(text_str)))
                page_num += 1
                page_text = []
                current_len = 0

        if page_text:
            text_str = "\n\n".join(page_text)
            pages.append(PageContent(page_number=page_num, text=text_str, character_count=len(text_str)))

        return pages if pages else [PageContent(page_number=1, text=raw_text.strip(), character_count=len(raw_text))]

    @classmethod
    def _strip_html_pages(cls, pages: List[PageContent]) -> List[PageContent]:
        """Removes HTML markup so HTML uploads read as clean text."""
        cleaned: List[PageContent] = []
        for page in pages:
            text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', ' ', page.text)
            text = re.sub(r'(?s)<[^>]*>', ' ', text)
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
            cleaned.append(PageContent(
                page_number=page.page_number,
                text=text or page.text,
                character_count=len(text or page.text),
            ))
        return cleaned

    # ================================================================== #
    # Section detection (improved)
    # ================================================================== #
    @classmethod
    def _detect_sections(cls, pages: List[PageContent]) -> List[DocumentSection]:
        sections = []
        seen_titles = set()

        for page in pages:
            text = page.text
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            for line in lines:
                if len(line) > 80 or len(line) < 3:
                    continue

                is_section = False

                # Check against all section patterns
                for pattern in cls._SECTION_PATTERNS:
                    if pattern.match(line):
                        is_section = True
                        break

                # Also detect lines that are likely headings:
                # - Short lines in ALL CAPS (4+ chars)
                # - Lines ending with a colon that look like headers
                if not is_section:
                    stripped = line.strip(":.- ")
                    if (
                        len(stripped) >= 4
                        and len(stripped) <= 60
                        and stripped.isupper()
                        and not stripped.startswith("[")
                    ):
                        is_section = True

                if is_section:
                    title = line.strip(":.- ").strip()
                    # Deduplicate
                    title_key = title.lower()
                    if title_key in seen_titles:
                        continue
                    seen_titles.add(title_key)

                    sections.append(DocumentSection(
                        title=title,
                        start_page=page.page_number,
                        end_page=page.page_number,
                        content=""
                    ))

        if not sections:
            sections.append(DocumentSection(
                title="General Terms",
                start_page=1,
                end_page=len(pages),
                content=""
            ))

        # Update end_page: each section extends until the next section starts
        for i in range(len(sections) - 1):
            sections[i].end_page = sections[i + 1].start_page

        return sections[:25]  # Top detected section boundaries

    # ================================================================== #
    # Clause detection (comprehensive, with full body text)
    # ================================================================== #
    @classmethod
    def _detect_clauses_full(cls, pages: List[PageContent], sections: List[DocumentSection]) -> List[DocumentClause]:
        """
        Detects clauses using multiple patterns and captures the FULL clause
        body text (not just the title line). Each clause's text extends from
        its header until the next detected clause header or end of page.
        """
        # First pass: find all clause header positions across all pages
        raw_matches: List[Tuple[int, int, str, str, str]] = []  # (page_num, char_offset, clause_id, title, full_line)

        for page in pages:
            text = page.text
            if not text or text.startswith("[") and "scanned" in text.lower():
                continue

            for pattern in cls._CLAUSE_PATTERNS:
                for match in pattern.finditer(text):
                    clause_id = match.group(1).strip()
                    title = match.group(2).strip()
                    raw_matches.append((
                        page.page_number,
                        match.start(),
                        clause_id,
                        title,
                        match.group(0).strip(),
                    ))

        # Deduplicate by (page, offset)
        seen = set()
        unique_matches: List[Tuple[int, int, str, str, str]] = []
        for entry in raw_matches:
            key = (entry[0], entry[1])
            if key not in seen:
                seen.add(key)
                unique_matches.append(entry)

        # Sort by page then offset
        unique_matches.sort(key=lambda x: (x[0], x[1]))

        # Second pass: extract full clause body text
        page_texts = {p.page_number: p.text for p in pages}
        clauses: List[DocumentClause] = []

        for i, (page_num, offset, clause_id, title, _full_line) in enumerate(unique_matches):
            page_text = page_texts.get(page_num, "")

            # Find the end of this clause: either the next clause on the same page,
            # or the end of the page text
            if i + 1 < len(unique_matches) and unique_matches[i + 1][0] == page_num:
                end_offset = unique_matches[i + 1][1]
            else:
                end_offset = len(page_text)

            # Extract the full clause body
            body = page_text[offset:end_offset].strip()

            # Limit body length to avoid huge chunks
            if len(body) > 2000:
                body = body[:2000] + "..."

            # Determine which section this clause belongs to
            section_name = cls._find_section_for_page(page_num, sections)

            clauses.append(DocumentClause(
                clause_id=clause_id,
                title=title[:80],
                page=page_num,
                section=section_name,
                text=body,
            ))

        # Cap at reasonable number
        return clauses[:60]

    @classmethod
    def _find_section_for_page(cls, page_num: int, sections: List[DocumentSection]) -> str:
        """Find the section that contains the given page number."""
        best = "General"
        for s in sections:
            if s.start_page <= page_num <= s.end_page:
                best = s.title
        # Return the last matching section (most specific)
        for s in reversed(sections):
            if s.start_page <= page_num:
                return s.title
        return best

    # Keep the old method signature for backward compatibility
    @classmethod
    def _detect_clauses(cls, pages: List[PageContent], sections: List[DocumentSection]) -> List[DocumentClause]:
        return cls._detect_clauses_full(pages, sections)

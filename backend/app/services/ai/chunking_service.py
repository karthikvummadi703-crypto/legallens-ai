import re
from typing import Any

from app.core.logging import logger
from app.models.document import ExtractedDocument


class LegalChunkingService:
    """
    Phase 4 (Optimised): Legal-Document-Aware Chunking Strategy.
    Hierarchy: Document → Page → Section → Clause → Chunk.
    Preserves source metadata with every chunk for precision grounding.

    Optimisations:
    - Larger 1500-char chunks (legal clauses are often 500-1500 chars)
    - 200-char overlap for better context continuity
    - Sentence-boundary splitting (never splits mid-sentence)
    - Contextual header prepend (section/clause title in each chunk)
    - Table-aware chunking (keeps table rows together)
    """

    MAX_CHUNK_SIZE = 1500  # Target max characters per chunk (up from 900)
    OVERLAP_SIZE = 200  # Character overlap between chunks (up from 150)

    # Simple sentence boundary pattern — splits on period/question/exclamation
    # followed by whitespace and a capital letter (avoids splitting on abbreviations
    # like "U.S." or "No. 5")
    _SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\'\(])")

    @classmethod
    def create_chunks(cls, extracted_doc: ExtractedDocument, user_id: str) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        chunk_index = 0

        doc_id = extracted_doc.document_id
        clauses_by_page = cls._map_clauses_by_page(extracted_doc)

        for page in extracted_doc.pages:
            page_num = page.page_number
            page_text = page.text.strip()
            if not page_text or (page_text.startswith("[") and "scanned" in page_text.lower()):
                continue

            # Check for clauses on this page
            page_clauses = clauses_by_page.get(page_num, [])

            if page_clauses:
                for clause in page_clauses:
                    clause_text = clause.text if hasattr(clause, "text") else str(clause)
                    c_id = getattr(clause, "clause_id", "")
                    c_sec = getattr(clause, "section", "General")
                    c_title = getattr(clause, "title", "")

                    # Prepend section/clause header for embedding context
                    header = cls._build_header(c_sec, c_title, c_id)

                    if len(clause_text) <= cls.MAX_CHUNK_SIZE:
                        # Prepend header to chunk text for richer embeddings
                        enriched_text = f"{header}\n{clause_text}" if header else clause_text
                        chunks.append(
                            {
                                "chunk_id": f"{doc_id}_chk_{chunk_index}",
                                "document_id": doc_id,
                                "user_id": user_id,
                                "page_number": page_num,
                                "section": c_sec,
                                "clause_id": c_id,
                                "text": enriched_text,
                                "chunk_index": chunk_index,
                            }
                        )
                        chunk_index += 1
                    else:
                        # Split large clause at sentence boundaries with overlap
                        sub_chunks = cls._split_at_sentences(clause_text)
                        for sub_txt in sub_chunks:
                            enriched_text = f"{header}\n{sub_txt}" if header else sub_txt
                            chunks.append(
                                {
                                    "chunk_id": f"{doc_id}_chk_{chunk_index}",
                                    "document_id": doc_id,
                                    "user_id": user_id,
                                    "page_number": page_num,
                                    "section": c_sec,
                                    "clause_id": c_id,
                                    "text": enriched_text,
                                    "chunk_index": chunk_index,
                                }
                            )
                            chunk_index += 1
            else:
                # No specific clause detected; chunk page text intelligently
                section_name = cls._detect_page_section(page_text)
                header = cls._build_header(section_name, "", "")

                # Check if the page contains tables — keep tables as intact chunks
                if "[TABLE]" in page_text:
                    table_chunks, non_table_text = cls._extract_table_chunks(page_text)
                    for t_chunk in table_chunks:
                        enriched = f"{header}\n{t_chunk}" if header else t_chunk
                        chunks.append(
                            {
                                "chunk_id": f"{doc_id}_chk_{chunk_index}",
                                "document_id": doc_id,
                                "user_id": user_id,
                                "page_number": page_num,
                                "section": section_name,
                                "clause_id": "",
                                "text": enriched,
                                "chunk_index": chunk_index,
                            }
                        )
                        chunk_index += 1
                    page_text = non_table_text  # Process remaining text normally

                # Split remaining text into paragraph-based chunks
                paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]
                current_text = ""

                for para in paragraphs:
                    if len(current_text) + len(para) <= cls.MAX_CHUNK_SIZE:
                        current_text += ("\n\n" + para) if current_text else para
                    else:
                        if current_text:
                            enriched = (
                                f"{header}\n{current_text.strip()}"
                                if header
                                else current_text.strip()
                            )
                            chunks.append(
                                {
                                    "chunk_id": f"{doc_id}_chk_{chunk_index}",
                                    "document_id": doc_id,
                                    "user_id": user_id,
                                    "page_number": page_num,
                                    "section": section_name,
                                    "clause_id": "",
                                    "text": enriched,
                                    "chunk_index": chunk_index,
                                }
                            )
                            chunk_index += 1
                        current_text = para

                if current_text:
                    enriched = (
                        f"{header}\n{current_text.strip()}" if header else current_text.strip()
                    )
                    chunks.append(
                        {
                            "chunk_id": f"{doc_id}_chk_{chunk_index}",
                            "document_id": doc_id,
                            "user_id": user_id,
                            "page_number": page_num,
                            "section": section_name,
                            "clause_id": "",
                            "text": enriched,
                            "chunk_index": chunk_index,
                        }
                    )
                    chunk_index += 1

        logger.info(f"Chunking complete: Created {len(chunks)} legal chunks for document {doc_id}.")
        return chunks

    @classmethod
    def _build_header(cls, section: str, title: str, clause_id: str) -> str:
        """Build a contextual header to prepend to each chunk for richer embeddings."""
        parts = []
        if section and section != "General" and section != "General Terms":
            parts.append(f"Section: {section}")
        if clause_id:
            parts.append(f"Clause {clause_id}")
        if title:
            parts.append(title)
        return " | ".join(parts) if parts else ""

    @classmethod
    def _extract_table_chunks(cls, text: str) -> tuple:
        """Separate table blocks from regular text. Returns (table_chunks, remaining_text)."""
        table_pattern = re.compile(r"\[TABLE\](.*?)\[/TABLE\]", re.DOTALL)
        tables = []
        for match in table_pattern.finditer(text):
            table_text = match.group(0).strip()
            if len(table_text) > cls.MAX_CHUNK_SIZE:
                # Split very large tables
                tables.extend(cls._split_at_sentences(table_text))
            else:
                tables.append(table_text)

        # Remove tables from the text to get the remaining
        remaining = table_pattern.sub("", text).strip()
        return tables, remaining

    @classmethod
    def _map_clauses_by_page(cls, doc: ExtractedDocument) -> dict[int, list]:
        mapping = {}
        for clause in getattr(doc, "clauses", []):
            pg = getattr(clause, "page", 1)
            if pg not in mapping:
                mapping[pg] = []
            mapping[pg].append(clause)
        return mapping

    @classmethod
    def _detect_page_section(cls, text: str) -> str:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:5]:
            if len(line) < 80 and re.match(
                r"^(?:SECTION|ARTICLE|CLAUSE|Part|Schedule|"
                r"\d+[\.\)]\s|#{1,4}\s|[A-Z][A-Z\s]{3,30}$)",
                line,
            ):
                return line.strip(":.- ")
        return "General Terms"

    @classmethod
    def _split_at_sentences(cls, text: str) -> list[str]:
        """
        Split text at sentence boundaries with overlap.
        Never splits mid-sentence.
        """
        sentences = cls._SENTENCE_RE.split(text)
        if len(sentences) <= 1:
            # Fallback to character-based splitting if no sentences detected
            return cls._split_with_overlap(text)

        sub_chunks = []
        current = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current) + len(sentence) + 1 <= cls.MAX_CHUNK_SIZE:
                current = (current + " " + sentence).strip() if current else sentence
            else:
                if current:
                    sub_chunks.append(current)
                    # Overlap: keep last portion of current chunk
                    overlap_text = cls._get_overlap_text(current)
                    current = (overlap_text + " " + sentence).strip() if overlap_text else sentence
                else:
                    # Single sentence exceeds max size
                    current = sentence

        if current:
            sub_chunks.append(current)

        return sub_chunks if sub_chunks else [text]

    @classmethod
    def _get_overlap_text(cls, text: str) -> str:
        """Get the last ~OVERLAP_SIZE characters worth of complete sentences for overlap."""
        if len(text) <= cls.OVERLAP_SIZE:
            return text
        # Take the last OVERLAP_SIZE characters
        tail = text[-cls.OVERLAP_SIZE :]
        # Find the first sentence boundary in the tail
        match = cls._SENTENCE_RE.search(tail)
        if match:
            return tail[match.start() :].strip()
        return tail.strip()

    @classmethod
    def _split_with_overlap(cls, text: str) -> list[str]:
        """Fallback character-based splitting with overlap."""
        sub_chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + cls.MAX_CHUNK_SIZE, text_len)
            sub_chunks.append(text[start:end].strip())
            if end >= text_len:
                break
            start += cls.MAX_CHUNK_SIZE - cls.OVERLAP_SIZE
        return sub_chunks

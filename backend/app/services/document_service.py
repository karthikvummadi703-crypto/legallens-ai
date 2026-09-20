import json
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime

from fastapi import UploadFile

from app.config import settings
from app.core.logging import logger
from app.models.document import DocumentMetadataResponse, ExtractedDocument
from app.services.ai.chunking_service import LegalChunkingService
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.gemini_service import GeminiAnalysisService
from app.services.ai.schemas import ChecklistItemData, FullDocumentAnalysis
from app.services.ai.vector_service import VectorDatabaseService
from app.services.extraction_service import DocumentExtractionService
from app.utils import cloud_store
from app.utils.file_utils import sanitize_filename

DB_FILE_PATH = os.path.join(settings.DATA_DIR, "db.json")

# Guard concurrent JSON DB reads/writes from multiple requests.
_db_lock = threading.RLock()

# Small in-process cache for the JSON DB. Each RAG/ask turn reads the DB
# several times; parsing db.json on every read loaded it repeatedly. Reads are
# served from cache for _DB_CACHE_TTL_SECONDS, and every save refreshes it
# immediately. The cache is keyed by DB_FILE_PATH so switching paths (tests,
# multiple DATA_DIRs) can never serve stale data, and writes from other
# processes/workers are seen again once the TTL expires. Cloud (RTDB) mode is
# intentionally NOT cached: each call still reads the live sections, so the
# multi-instance serverless behaviour is unchanged.
_db_cache: dict | None = None
_DB_CACHE_TTL_SECONDS = 2.0


def _reset_db_cache() -> None:
    """Drop the in-memory cache (used by tests and path switches)."""
    global _db_cache
    _db_cache = None


def _load_db() -> dict:
    if cloud_store.is_cloud_mode():
        return cloud_store.get_db_sections()
    global _db_cache
    with _db_lock:
        now = time.monotonic()
        if _db_cache is not None and _db_cache["key"] == DB_FILE_PATH:
            if now - _db_cache["ts"] <= _DB_CACHE_TTL_SECONDS:
                return _db_cache["data"]
        if os.path.exists(DB_FILE_PATH):
            try:
                with open(DB_FILE_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    if "documents" not in data:
                        data["documents"] = {}
                    if "analyses" not in data:
                        data["analyses"] = {}
                    if "conversations" not in data:
                        data["conversations"] = {}
                    _db_cache = {"key": DB_FILE_PATH, "ts": now, "data": data}
                    return data
            except Exception as e:
                # Never silently reset a corrupt DB (that would wipe every
                # user's uploads + chat history). Back it up for recovery.
                try:
                    backup = DB_FILE_PATH + ".corrupt.bak"
                    with (
                        open(DB_FILE_PATH, encoding="utf-8") as src,
                        open(backup, "w", encoding="utf-8") as dst,
                    ):
                        dst.write(src.read())
                    logger.error(f"DB file corrupt; backed up to {backup}: {e}")
                except Exception:
                    logger.error(f"DB file corrupt and backup failed: {e}")
    return {"documents": {}, "analyses": {}, "conversations": {}}


def _save_db(data: dict):
    if cloud_store.is_cloud_mode():
        cloud_store.save_db_sections(data)
        return
    global _db_cache
    with _db_lock:
        # Atomic write: crash during save can no longer truncate db.json.
        tmp_path = DB_FILE_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, DB_FILE_PATH)
        _db_cache = {"key": DB_FILE_PATH, "ts": time.monotonic(), "data": data}


class DocumentManager:
    @classmethod
    async def process_and_save_upload(
        cls, file: UploadFile, content: bytes, user_id: str
    ) -> DocumentMetadataResponse:
        doc_id = f"doc-{uuid.uuid4().hex[:8]}"
        original_filename = file.filename or "uploaded_document.pdf"
        filename = sanitize_filename(original_filename) or f"document{uuid.uuid4().hex[:8]}"
        ext = os.path.splitext(filename)[1].lower()

        # Save raw uploaded file. Cloud mode persists the file to Firebase
        # RTDB (serverless FS is read-only/ephemeral) and extracts from a
        # /tmp copy; local mode keeps the historical on-disk behaviour.
        cloud_mode = cloud_store.is_cloud_mode()
        saved_file_path = None
        if cloud_mode:
            blob_name = f"uploads/{user_id}/{doc_id}_{filename}"
            try:
                cloud_store.blob_upload(blob_name, content)
            except Exception as e:
                logger.error(f"Failed to persist uploaded file to Firebase: {e}")
                raise ValueError("Failed to persist uploaded file.")
            saved_file_path = blob_name
            extract_path = os.path.join(tempfile.gettempdir(), f"{doc_id}_{filename}")
            with open(extract_path, "wb") as f:
                f.write(content)
            try:
                extracted = DocumentExtractionService.extract_document(
                    extract_path, doc_id, filename
                )
            finally:
                try:
                    os.remove(extract_path)
                except Exception:
                    pass
        else:
            user_upload_dir = os.path.join(settings.UPLOAD_DIR, user_id)
            os.makedirs(user_upload_dir, exist_ok=True)
            saved_file_path = os.path.join(user_upload_dir, f"{doc_id}_{filename}")
            try:
                with open(saved_file_path, "wb") as f:
                    f.write(content)
            except Exception as e:
                logger.error(f"Failed to write uploaded file {saved_file_path}: {e}")
                raise ValueError("Failed to persist uploaded file.")
            # Execute Phase 2 extraction (clean up partial file if extraction fails)
            try:
                extracted = DocumentExtractionService.extract_document(
                    saved_file_path, doc_id, filename
                )
            except Exception as e:
                logger.error(f"Extraction failed for {doc_id}: {e}")
                try:
                    os.remove(saved_file_path)
                except Exception:
                    pass
                raise

        # Format document metadata response
        file_size_mb = len(content) / (1024 * 1024)
        size_str = (
            f"{file_size_mb:.1f} MB" if file_size_mb >= 1.0 else f"{int(len(content) / 1024)} KB"
        )

        lowered = filename.lower()
        if any(k in lowered for k in ("employment", "offer", "appointment", "hr", "resume", "cv")):
            category = "Employment"
        elif any(k in lowered for k in ("lease", "rent", "property", "estate", "mortgage", "deed")):
            category = "Real Estate"
        elif any(
            k in lowered
            for k in (
                "saas",
                "vendor",
                "supplier",
                "service",
                "subscription",
                "license",
                "msa",
                "consult",
            )
        ):
            category = "Vendor & SaaS"
        elif any(k in lowered for k in ("nda", "confidential", "non-disclosure", "privacy")):
            category = "Confidentiality"
        else:
            category = "Corporate"

        meta = DocumentMetadataResponse(
            id=doc_id,
            name=filename,
            type="TXT"
            if ext in (".md", ".markdown", ".csv", ".html", ".htm", ".log")
            else ext.replace(".", "").upper(),
            uploadDate=datetime.now().strftime("%b %d, %Y"),
            size=size_str,
            analysisStatus="Processing",
            indexingStatus="indexing",
            attentionScore=0,
            pageCount=extracted.total_pages,
            category=category,
            summary="Document processed and ready for AI analysis.",
            clausesCount=len(extracted.clauses),
            risksCount=0,
            obligationsCount=0,
        )

        db = _load_db()
        db["documents"][doc_id] = {
            "metadata": meta.model_dump(),
            "extracted": extracted.model_dump(),
            "user_id": user_id,
            "saved_path": saved_file_path,
        }
        _save_db(db)

        # Phase 4 Indexing Pipeline: Create chunks, generate embeddings, store in Qdrant
        try:
            cls.index_document(doc_id, user_id)
        except Exception as e:
            logger.error(f"Vector indexing failed for document {doc_id}: {e}")
            db = _load_db()
            if doc_id in db.get("documents", {}):
                db["documents"][doc_id]["metadata"]["indexingStatus"] = "indexing_failed"
                _save_db(db)

        return meta

    @classmethod
    def index_document(cls, doc_id: str, user_id: str) -> bool:
        entry = cls.get_document_by_id(doc_id, user_id)
        if not entry:
            raise ValueError(f"Document {doc_id} not found.")

        extracted = ExtractedDocument(**entry["extracted"])
        chunks = LegalChunkingService.create_chunks(extracted, user_id)

        chunk_texts = [c["text"] for c in chunks]
        embeddings = EmbeddingService.generate_embeddings(chunk_texts)

        doc_name = entry.get("metadata", {}).get("name", "")
        success = VectorDatabaseService.upsert_document_chunks(
            user_id, doc_id, chunks, embeddings, document_name=doc_name
        )

        db = _load_db()
        if doc_id in db.get("documents", {}):
            db["documents"][doc_id]["metadata"]["indexingStatus"] = (
                "indexed" if success else "indexing_failed"
            )
            _save_db(db)

        return success

    @classmethod
    def reindex_document(cls, doc_id: str, user_id: str) -> bool:
        VectorDatabaseService.delete_document_vectors(user_id, doc_id)
        return cls.index_document(doc_id, user_id)

    @classmethod
    def get_user_documents(cls, user_id: str) -> list[DocumentMetadataResponse]:
        db = _load_db()
        docs = []
        for _doc_id, entry in db.get("documents", {}).items():
            if entry.get("user_id") == user_id:
                docs.append(DocumentMetadataResponse(**entry["metadata"]))
        return docs

    @classmethod
    def get_document_by_id(cls, doc_id: str, user_id: str) -> dict | None:
        db = _load_db()
        entry = db.get("documents", {}).get(doc_id)
        if entry and entry.get("user_id") == user_id:
            return entry
        return None

    @classmethod
    async def analyze_document(cls, doc_id: str, user_id: str) -> FullDocumentAnalysis:
        entry = cls.get_document_by_id(doc_id, user_id)
        if not entry:
            raise ValueError(f"Document {doc_id} not found or unauthorized.")

        extracted = ExtractedDocument(**entry["extracted"])
        analysis = await GeminiAnalysisService.analyze_document(extracted, user_id)

        # Update metadata in DB with analysis results
        db = _load_db()
        if doc_id in db["documents"]:
            meta = db["documents"][doc_id]["metadata"]
            meta["analysisStatus"] = "Analyzed"
            meta["attentionScore"] = analysis.attention_score.score
            meta["summary"] = analysis.executive_summary.summary
            meta["clausesCount"] = len(analysis.important_clauses)
            meta["risksCount"] = len(analysis.potential_risks)
            meta["obligationsCount"] = len(analysis.obligations)
            db["analyses"][doc_id] = analysis.model_dump()
            _save_db(db)

        return analysis

    @classmethod
    def get_document_analysis(cls, doc_id: str, user_id: str) -> FullDocumentAnalysis | None:
        db = _load_db()
        # Verify ownership
        entry = db.get("documents", {}).get(doc_id)
        if not entry or entry.get("user_id") != user_id:
            return None
        analysis_data = db.get("analyses", {}).get(doc_id)
        if analysis_data:
            return FullDocumentAnalysis(**analysis_data)
        return None

    @classmethod
    def get_document_checklist(cls, doc_id: str, user_id: str) -> list[ChecklistItemData]:
        """
        Builds an actionable pre-signing checklist from the stored document
        analysis. Returns an empty list when the document has not been
        analyzed yet — never fabricated items.
        """
        analysis = cls.get_document_analysis(doc_id, user_id)
        if not analysis:
            return []

        items: list[ChecklistItemData] = []

        def _add(
            section: str, title: str, explanation: str, page: int, section_ref: str, attention: str
        ):
            items.append(
                ChecklistItemData(
                    id=f"chk-{len(items) + 1}",
                    section=section,
                    title=title,
                    explanation=explanation,
                    page=page or 1,
                    section_ref=section_ref or "General",
                    attention_level=attention,  # type: ignore[arg-type]
                    completed=False,
                )
            )

        for ob in analysis.obligations:
            _add(
                "Obligations",
                f"Review obligation: {ob.obligation[:80]}",
                f"The document requires: {ob.obligation} Deadline: {ob.deadline}. "
                f"Consequence of non-compliance: {ob.consequence}.",
                ob.page,
                ob.section,
                "medium",
            )

        for p in analysis.payments:
            _add(
                "Payments",
                f"Verify payment term: {p.item[:80]}",
                f"Amount: {p.amount} ({p.frequency}). Due: {p.due_date}. Late fees: {p.late_fees}.",
                p.page,
                p.section,
                "medium",
            )

        for kd in analysis.key_dates:
            _add(
                "Term",
                f"Calendar deadline: {kd.event[:80]}",
                f"{kd.event}: {kd.date_or_period}. Missing this date may carry consequences "
                "described in the document.",
                kd.page,
                kd.section,
                kd.importance if kd.importance in ("high", "medium", "low") else "medium",
            )

        for r in analysis.potential_risks:
            section = (
                r.category
                if r.category
                in (
                    "Payments",
                    "Term",
                    "Termination",
                    "Obligations",
                    "Liability",
                    "Dispute Resolution",
                )
                else "Liability"
            )
            _add(
                section,
                f"Examine flagged concern: {r.title[:80]}",
                f"{r.explanation} Practical impact: {r.why_it_matters}",
                r.page,
                r.section,
                r.severity if r.severity in ("high", "medium", "low") else "medium",
            )

        term = analysis.termination_analysis
        if term and "no termination provision" not in (term.summary or "").lower():
            _add(
                "Termination",
                "Confirm termination rights and penalties",
                f"Who can terminate: {term.who_can_terminate}. Notice: {term.notice_period}. "
                f"Penalties: {term.penalties}. Cure period: {term.cure_period}.",
                term.page,
                term.section,
                "high",
            )

        renewal = analysis.renewal_analysis
        if renewal and renewal.has_renewal:
            _add(
                "Term",
                "Calendar the renewal opt-out deadline",
                f"Renewal summary: {renewal.summary} Notice required: {renewal.notice_period}. "
                f"Opt-out method: {renewal.opt_out}.",
                renewal.page,
                renewal.section,
                "medium",
            )

        return items

    @classmethod
    def delete_document(cls, doc_id: str, user_id: str) -> bool:
        db = _load_db()
        entry = db.get("documents", {}).get(doc_id)
        if not entry or entry.get("user_id") != user_id:
            return False

        # Clean up the stored file if it exists. Cloud mode deletes the
        # persisted file node when saved_path holds a cloud name, otherwise
        # removes the local file.
        saved_path = entry.get("saved_path")
        if saved_path:
            if cloud_store.is_cloud_mode():
                try:
                    cloud_store.blob_delete(saved_path)
                except Exception:
                    pass
            elif os.path.exists(saved_path):
                try:
                    os.remove(saved_path)
                except Exception:
                    pass

        # Purge vector embeddings from Qdrant
        VectorDatabaseService.delete_document_vectors(user_id, doc_id)

        # Purge conversation history
        from app.services.ai.rag_service import RAGService

        RAGService.delete_conversation_history(user_id, doc_id)

        del db["documents"][doc_id]
        if doc_id in db.get("analyses", {}):
            del db["analyses"][doc_id]
        _save_db(db)
        return True

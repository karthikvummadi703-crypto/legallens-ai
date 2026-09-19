import asyncio
import json
import time
import uuid
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.config import settings
from app.core.logging import logger
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.vector_service import VectorDatabaseService
from app.services.ai.prompts import SYSTEM_RAG_PROMPT, RAG_USER_PROMPT_TEMPLATE
from app.services.ai.gemini_keys import gemini_key_manager
from app.services.document_service import DB_FILE_PATH, _load_db, _save_db

class SourceCitation(BaseModel):
    page: int = Field(default=1)
    section: str = Field(default="General")
    clause_id: Optional[str] = Field(default="")
    snippet: str = Field(default="")
    document_id: str = Field(default="")
    document_name: str = Field(default="")

class RAGAnswerResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: List[SourceCitation] = Field(default_factory=list)
    confidence: str = Field(default="high")
    followup_questions: List[str] = Field(default_factory=list)

class RAGService:
    """
    Phase 4: Retrieval-Augmented Generation (RAG) + Ask LegalLens Service.
    Handles question processing, vector search, Gemini context generation,
    source citations, and conversational history.
    """

    TOP_K = 8
    CROSS_DOC_TOP_K = 10

    # Tokens that carry little disambiguating power on their own (e.g. a user
    # saying "my contract" while owning several contracts/agreements). A match
    # based ONLY on such tokens should be treated as ambiguous across the library.
    GENERIC_DOC_TOKENS = frozenset({
        "contract", "agreement", "document", "documents", "agreements", "contracts",
        "file", "files", "lease", "letter", "letters", "policy", "policies", "terms",
        "term", "form", "forms", "report", "reports", "deed", "deeds", "clause",
        "clauses", "section", "sections", "request", "requests", "claim", "claims",
        "petition", "petitions", "order", "orders", "notice", "notices", "standard",
        "template", "templates",
    })

    # ------------------------------------------------------------------
    # Document scope detection (natural-language reference resolution)
    # ------------------------------------------------------------------
    @classmethod
    def _normalize_doc_name(cls, name: str) -> str:
        base = name.rsplit(".", 1)[0]
        base = re.sub(r"[_\-\.]+", " ", base)
        return base.lower().strip()

    @classmethod
    def _detect_referenced_docs(cls, question: str, library_map: dict, selected_document_id: Optional[str] = None) -> dict:
        """
        Returns {mode, doc_ids, ambiguous, reason}
        mode: 'specific' (selected doc only) | 'single_referenced' | 'multi' | 'all'
        """
        q_lower = question.lower()
        cross_signals = ["compare", "both", "each", "all documents", "all my documents",
                         "any of my", "which documents", "which of my", "every document",
                         "across my documents", "between", "summarize my"]
        has_cross_signal = any(sig in q_lower for sig in cross_signals)
        # Detect explicit doc mentions via token overlap + substring
        matches = []
        for doc_id, doc_name in library_map.items():
            norm = cls._normalize_doc_name(doc_name)
            tokens = [t for t in norm.split() if len(t) > 2]
            if not tokens:
                continue
            hit_tokens = sum(1 for t in tokens if t in q_lower)
            score = hit_tokens / len(tokens) if tokens else 0
            # Boost for exact normalized name substring or abbreviation like NDA
            if norm in q_lower:
                score = 1.0
            # Single-token doc like NDA.pdf -> norm = "nda"
            if len(tokens) == 1 and tokens[0] in q_lower:
                score = 1.0
            if score >= 0.5:
                matches.append((doc_id, doc_name, score))
        # Cross-document signals take precedence over generic ambiguous
        if has_cross_signal and len(matches) >= 2:
            return {"mode": "multi", "doc_ids": [m[0] for m in matches], "ambiguous": False, "reason": "cross_signal_multi"}
        if has_cross_signal and len(matches) == 1:
            if any(kw in q_lower for kw in ["compare", "both", "between", "difference"]):
                return {"mode": "all", "doc_ids": list(library_map.keys()), "ambiguous": False, "reason": "compare_single_match_fallback_all"}
            return {"mode": "single_referenced", "doc_ids": [matches[0][0]], "ambiguous": False, "reason": "single_with_cross_signal"}
        if has_cross_signal:
            return {"mode": "all", "doc_ids": list(library_map.keys()), "ambiguous": False, "reason": "cross_signal_all"}
        # Generic vague reference without cross-signal: ambiguous if multiple docs and no specific match
        if not matches and re.search(r"\bmy (contract|document|file|agreement|lease)s?\b", q_lower):
            if len(library_map) > 1:
                # But phrases like "which documents" already handled above, so only generic singular
                if not re.search(r"\bwhich\b", q_lower):
                    return {"mode": "ambiguous", "doc_ids": list(library_map.keys()), "ambiguous": True, "reason": "generic_reference"}
        # A match based ONLY on generic category tokens ("contract", "agreement"...) is a weak
        # match: it does not pick out one specific document when several exist.
        if len(matches) == 1 and len(library_map) > 1 and matches[0][2] < 1.0:
            doc_id, doc_name, _score = matches[0]
            norm = cls._normalize_doc_name(doc_name)
            if norm not in q_lower:
                weak_hits = [t for t in norm.split() if len(t) > 2 and t in q_lower and t in cls.GENERIC_DOC_TOKENS]
                non_weak_hits = [t for t in norm.split() if len(t) > 2 and t in q_lower and t not in cls.GENERIC_DOC_TOKENS]
                if weak_hits and not non_weak_hits:
                    return {"mode": "ambiguous", "doc_ids": list(library_map.keys()), "ambiguous": True, "reason": "generic_reference"}
        if len(matches) == 1:
            return {"mode": "single_referenced", "doc_ids": [matches[0][0]], "ambiguous": False, "reason": "single_reference"}
        if len(matches) >= 2:
            return {"mode": "multi", "doc_ids": [m[0] for m in matches], "ambiguous": False, "reason": "multi_reference"}
        # No explicit reference: use selected doc
        return {"mode": "specific", "doc_ids": [selected_document_id] if selected_document_id else [], "ambiguous": False, "reason": "no_reference_specific"}

    @classmethod
    async def ask_question(
        cls, 
        user_id: str, 
        document_id: str, 
        document_name: str,
        question: str, 
        conversation_id: Optional[str] = None
    ) -> RAGAnswerResponse:
        if not conversation_id:
            conversation_id = f"conv-{uuid.uuid4().hex[:8]}"

        # Diagnostic logging without secrets (truncated user, question snippet, scope)
        logger.info(f"RAG Q&A: user='{user_id[:8]}...' doc='{document_id}' conv='{conversation_id}' q='{question[:80]}'")

        # Local import avoids a circular dependency with document_service.
        from app.services.document_service import DocumentManager

        # 0. Indexing guard: never retrieve from a document that is not indexed yet.
        entry = DocumentManager.get_document_by_id(document_id, user_id)
        indexing_status = (entry.get("metadata", {}) if entry else {}).get("indexingStatus", "indexed")
        if indexing_status not in ("indexed",):
            answer_text = (
                f"That document is still being processed (status: {indexing_status}). "
                "Please wait until indexing is complete before asking questions about it."
            )
            result = RAGAnswerResponse(
                conversation_id=conversation_id,
                answer=f"{answer_text}\n\n*LegalLens provides informational assistance and does not replace professional legal advice.*",
                sources=[],
                confidence="low",
                followup_questions=["Which of my documents are ready to query?"]
            )
            cls._save_message_pair(user_id, document_id, conversation_id, question, result.answer, [])
            return result

        # 0b. Document-library awareness: names of ALL user-owned documents so the
        # model can resolve natural references ("my employment contract") and ask
        # for clarification when a reference is genuinely ambiguous.
        library_map = cls._user_library_map(user_id)
        library_names = list(library_map.values())
        library_text = (
            "Available user documents:\n" + "\n".join(f"- {n}" for n in library_names)
            if library_names else "Available user documents: (none besides the selected document)"
        )

        # Scope detection for intelligent routing
        scope = cls._detect_referenced_docs(question, library_map, selected_document_id=document_id)
        logger.info(f"Dev RAG Scope detect: mode='{scope['mode']}' doc_ids={scope['doc_ids']} reason='{scope['reason']}' q='{question[:60]}'")

        # Ambiguous reference -> ask clarification, do not hallucinate
        if scope.get("ambiguous"):
            doc_list = " or ".join([f"'{library_map[did]}'" for did in scope["doc_ids"][:3]])
            answer_text = f"Which document do you mean — {doc_list}?"
            result = RAGAnswerResponse(
                conversation_id=conversation_id,
                answer=f"{answer_text}\n\n*LegalLens provides informational assistance and does not replace professional legal advice.*",
                sources=[],
                confidence="low",
                followup_questions=[f"Summarize {library_map[did]}" for did in scope["doc_ids"][:2]]
            )
            cls._save_message_pair(user_id, document_id, conversation_id, question, result.answer, [])
            return result

        # Small talk first: greetings need conversation, not vector retrieval.
        if cls._is_small_talk(question):
            result = cls._small_talk_reply(question, conversation_id, document_name)
            cls._save_message_pair(user_id, document_id, conversation_id, question, result.answer, [])
            return result

        # 1. Generate Question Embedding with query expansion for follow-ups
        chat_history = cls.get_conversation_history(user_id, document_id, conversation_id)
        expanded_query = cls._expand_query_with_history(question, chat_history)
        query_vector = EmbeddingService.generate_embedding(expanded_query)

        # 2. Intelligent retrieval based on detected scope
        retrieved_chunks: List[Dict[str, Any]] = []
        retrieval_scope = "document"

        if scope["mode"] == "single_referenced":
            ref_id = scope["doc_ids"][0]
            if ref_id != document_id:
                # User asked about a different doc than selected -> search that doc directly
                # Check that referenced doc is indexed
                ref_entry = DocumentManager.get_document_by_id(ref_id, user_id)
                ref_status = (ref_entry.get("metadata", {}) if ref_entry else {}).get("indexingStatus", "indexed")
                if ref_status != "indexed":
                    answer_text = (
                        f"That document is still being processed (status: {ref_status}). "
                        "Please wait until indexing is complete before asking questions about it."
                    )
                    result = RAGAnswerResponse(
                        conversation_id=conversation_id,
                        answer=f"{answer_text}\n\n*LegalLens provides informational assistance and does not replace professional legal advice.*",
                        sources=[],
                        confidence="low",
                        followup_questions=["Which of my documents are ready to query?"]
                    )
                    cls._save_message_pair(user_id, document_id, conversation_id, question, result.answer, [])
                    return result
                retrieved_chunks = VectorDatabaseService.search_similar_chunks(
                    user_id=user_id, document_id=ref_id, query_vector=query_vector, top_k=cls.TOP_K
                )
                retrieval_scope = "cross-document"
                # If nothing in that specific doc, broaden to all docs (maybe question broader)
                if not retrieved_chunks:
                    cross_chunks = VectorDatabaseService.search_filtered_chunks(
                        user_id=user_id, document_ids=scope["doc_ids"], query_vector=query_vector, top_k=cls.CROSS_DOC_TOP_K
                    )
                    if cross_chunks:
                        retrieved_chunks = cross_chunks
                logger.info(f"RAG scope='{retrieval_scope}' single_referenced doc={ref_id} chunks={len(retrieved_chunks)}")
            else:
                # Referenced doc is same as selected -> normal doc search
                retrieved_chunks = VectorDatabaseService.search_similar_chunks(
                    user_id=user_id, document_id=document_id, query_vector=query_vector, top_k=cls.TOP_K
                )
                logger.info(f"RAG scope='document' (self-reference) chunks={len(retrieved_chunks)}")
        elif scope["mode"] in ("multi", "all"):
            target_ids = scope["doc_ids"] if scope["mode"] == "multi" else list(library_map.keys())
            if len(target_ids) == 1:
                retrieved_chunks = VectorDatabaseService.search_similar_chunks(
                    user_id=user_id, document_id=target_ids[0], query_vector=query_vector, top_k=cls.TOP_K
                )
                retrieval_scope = "document" if len(target_ids) == 1 else "cross-document"
            else:
                retrieved_chunks = VectorDatabaseService.search_filtered_chunks(
                    user_id=user_id, document_ids=target_ids, query_vector=query_vector, top_k=cls.CROSS_DOC_TOP_K
                )
                if not retrieved_chunks:
                    # Fallback to full user search if filtered yields nothing
                    retrieved_chunks = VectorDatabaseService.search_user_chunks(
                        user_id=user_id, query_vector=query_vector, top_k=cls.CROSS_DOC_TOP_K
                    )
                retrieval_scope = "cross-document"
            logger.info(f"RAG scope='{retrieval_scope}' multi/all docs={target_ids} chunks={len(retrieved_chunks)}")
        else:
            # mode == specific -> search selected doc first
            retrieved_chunks = VectorDatabaseService.search_similar_chunks(
                user_id=user_id,
                document_id=document_id,
                query_vector=query_vector,
                top_k=cls.TOP_K
            )
            retrieval_scope = "document"
            for idx, chunk in enumerate(retrieved_chunks):
                logger.info(f"Dev RAG Retrieval #{idx+1}: Score={chunk.get('score', 0):.4f} | Page={chunk.get('page_number')} | Sec={chunk.get('section')}")
            logger.info(f"RAG scope='{retrieval_scope}' doc_chunks={len(retrieved_chunks)}")
            # Strict isolation: do NOT fallback to other docs when selected doc has no hits.
            # Instead we return a grounded "not found in this document" answer below.

        # For non-fallback paths, still log chunks
        if scope["mode"] != "specific":
            for idx, chunk in enumerate(retrieved_chunks):
                logger.info(f"Dev RAG Retrieval #{idx+1}: Score={chunk.get('score', 0):.4f} | Doc={chunk.get('document_id')} | Page={chunk.get('page_number')} | Sec={chunk.get('section')}")

        # 3. Retrieve Recent Conversation History
        chat_history = cls.get_conversation_history(user_id, document_id, conversation_id)
        history_text = cls._format_chat_history(chat_history)

        # 4. Check if retrieved chunks are sufficient. Strict isolation:
        #    when the selected document has no relevant chunk, report honestly
        #    for THAT document (do not leak other docs). save=False keeps the
        #    doc-scoped conversation history intact.
        if not retrieved_chunks:
            from app.services.ai.general_chat_service import GeneralChatService
            general = await GeneralChatService.ask_pure_general(
                question, user_id, conversation_id, save=False
            )
            answer_text = (
                f"I couldn't find enough information about that in '{document_name}'. "
                "The document doesn't appear to contain relevant text for this question, "
                "so here is some general guidance that may help:\n\n"
                f"{general.answer}"
            )
            result = RAGAnswerResponse(
                conversation_id=conversation_id,
                answer=answer_text,
                sources=[
                    SourceCitation(
                        document_id=s.document_id,
                        document_name=s.document_name,
                        page=s.page,
                        section=s.section,
                        snippet=s.snippet,
                    )
                    for s in general.sources
                ],
                confidence=general.confidence,
                followup_questions=general.followup_questions or [
                    "What are the main obligations in this contract?",
                    "When does this agreement terminate?",
                ],
            )
            cls._save_message_pair(user_id, document_id, conversation_id, question, result.answer, [s.model_dump() for s in result.sources])
            return result

        # 5. Build Grounded Context (every block labelled with its document)
        if retrieval_scope == "cross-document":
            context_text = "\n\n".join([
                f"[Document: {cls._chunk_doc_name(c, user_id)}]\n"
                f"--- Snippet Page {c.get('page_number', 1)} • Section '{c.get('section', 'General')}' ---\n{c.get('text', '')}"
                for c in retrieved_chunks
            ])
            context_text = (
                f"{library_text}\n\n"
                "The excerpts below come from the user's document library. "
                "Attribute every claim to its labelled document; if the question names a document, "
                "prefer it, and if the reference is ambiguous between listed documents, ask which one is meant.\n\n"
                + context_text
            )
        else:
            context_text = "\n\n".join([
                f"--- Snippet Page {c.get('page_number', 1)} • Section '{c.get('section', 'General')}' ---\n{c.get('text', '')}"
                for c in retrieved_chunks
            ])
            context_text = f"{library_text}\n\n" + context_text

        # 6. Call Gemini API if keys are present (rotates on quota exhaustion)
        if gemini_key_manager.has_keys():
            for api_key in gemini_key_manager.iter_keys():
                try:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=api_key)
                    prompt = RAG_USER_PROMPT_TEMPLATE.format(
                        filename=document_name,
                        document_id=document_id,
                        context_text=context_text,
                        chat_history_text=history_text,
                        user_question=question
                    )

                    config = types.GenerateContentConfig(
                        system_instruction=SYSTEM_RAG_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.2,
                    )

                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=settings.GEMINI_MODEL,
                        contents=prompt,
                        config=config
                    )

                    if response and response.text:
                        parsed = cls._parse_rag_json(response.text, conversation_id, retrieved_chunks)
                        if parsed:
                            gemini_key_manager.report_success(api_key)
                            if retrieval_scope == "cross-document":
                                parsed.sources = cls._attribute_sources(
                                    parsed.sources, retrieved_chunks, user_id
                                )
                            cls._save_message_pair(
                                user_id, document_id, conversation_id, question,
                                parsed.answer, [s.model_dump() for s in parsed.sources],
                                referenced=list({c.get("document_id", "") for c in retrieved_chunks if c.get("document_id")}),
                            )
                            return parsed
                    break  # non-quota path done (parsed or empty); fall through to fallback
                except Exception as e:
                    if gemini_key_manager.is_quota_error(e):
                        gemini_key_manager.report_quota_failure(api_key)
                        continue  # quota exhausted -> fail over to next key
                    logger.error(f"Gemini RAG SDK error ({e}). Using grounded snippet synthesis engine.")
                    break

        # 7. Fallback grounded answer derived directly from top matching chunks,
        # enriched with stored document intelligence so the chatbot doubles as
        # a legal advisor even when the live AI service is unreachable.
        result = cls._generate_grounded_fallback_rag(question, retrieved_chunks, conversation_id)
        if retrieval_scope == "cross-document":
            result.sources = cls._attribute_sources(result.sources, retrieved_chunks, user_id)
            top_doc = cls._chunk_doc_name(retrieved_chunks[0], user_id)
            result.answer = (
                f"Based on your uploaded document '{top_doc}' (and related library excerpts):\n\n"
                + result.answer
            )
        # Legal-advisor enrichment: append concrete analysed data for the
        # documents actually consulted, so the answer carries real figures,
        # risks and deadlines instead of only a raw excerpt.
        intel_doc_ids = [c.get("document_id", "") for c in retrieved_chunks if c.get("document_id")]
        if document_id and document_id not in intel_doc_ids:
            intel_doc_ids.append(document_id)
        intel = cls._advisor_intel_block(user_id, intel_doc_ids)
        if intel and "informational assistance" in result.answer:
            result.answer = result.answer.replace(
                "*LegalLens provides informational assistance and does not replace professional legal advice.*",
                f"{intel.strip()}\n\n*LegalLens provides informational assistance and does not replace professional legal advice.*",
            )
        if cls._is_advice_question(question) and intel:
            result.followup_questions = [
                "What are the biggest risks in this document?",
                "What should I check before signing?",
                "What questions should I ask a lawyer about this?",
            ]
        cls._save_message_pair(
            user_id, document_id, conversation_id, question,
            result.answer, [s.model_dump() for s in result.sources],
            referenced=list({c.get("document_id", "") for c in retrieved_chunks if c.get("document_id")}),
        )
        return result

    @classmethod
    async def ask_unified(
        cls,
        user_id: str,
        question: str,
        selected_document_id: Optional[str] = None,
        selected_document_name: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> RAGAnswerResponse:
        """
        Unified library-aware Q&A used by POST /api/chat/query.
        If a selected document is provided, delegates to the intelligent
        ask_question (which already does reference-aware routing).
        If no selection, performs cross-document retrieval across the full
        user library and answers with per-document attribution.
        """
        if selected_document_id:
            # Resolve name if not provided
            doc_name = selected_document_name
            if not doc_name:
                try:
                    from app.services.document_service import DocumentManager
                    entry = DocumentManager.get_document_by_id(selected_document_id, user_id)
                    doc_name = (entry.get("metadata", {}) if entry else {}).get("name", selected_document_id)
                except Exception:
                    doc_name = selected_document_id
            return await cls.ask_question(
                user_id=user_id,
                document_id=selected_document_id,
                document_name=doc_name or selected_document_id,
                question=question,
                conversation_id=conversation_id
            )
        # No selected doc: library-wide retrieval
        if not conversation_id:
            conversation_id = f"conv-{uuid.uuid4().hex[:8]}"
        logger.info(f"Unified RAG (library-wide): user='{user_id[:8]}...' conv='{conversation_id}' q='{question[:80]}'")
        library_map = cls._user_library_map(user_id)
        library_names = list(library_map.values())
        library_text = (
            "Available user documents:\n" + "\n".join(f"- {n}" for n in library_names)
            if library_names else "Available user documents: (none)"
        )
        scope = cls._detect_referenced_docs(question, library_map, selected_document_id=None)
        logger.info(f"Unified scope: mode='{scope['mode']}' doc_ids={scope['doc_ids']} reason='{scope['reason']}'")
        if scope.get("ambiguous"):
            doc_list = " or ".join([f"'{library_map[did]}'" for did in scope["doc_ids"][:3]])
            answer_text = f"Which document do you mean — {doc_list}?"
            result = RAGAnswerResponse(
                conversation_id=conversation_id,
                answer=f"{answer_text}\n\n*LegalLens provides informational assistance and does not replace professional legal advice.*",
                sources=[], confidence="low",
                followup_questions=[f"Summarize {library_map[did]}" for did in scope["doc_ids"][:2]]
            )
            cls._save_message_pair(user_id, None, conversation_id, question, result.answer, [])
            return result

        # Small talk first: greetings need conversation, not vector retrieval.
        if cls._is_small_talk(question):
            result = cls._small_talk_reply(question, conversation_id)
            cls._save_message_pair(user_id, None, conversation_id, question, result.answer, [])
            return result

        chat_history = cls.get_conversation_history(user_id, None, conversation_id)
        expanded_query = cls._expand_query_with_history(question, chat_history)
        query_vector = EmbeddingService.generate_embedding(expanded_query)
        retrieved_chunks: List[Dict[str, Any]] = []
        if scope["mode"] in ("single_referenced", "multi", "all"):
            target_ids = scope["doc_ids"] if scope["mode"] != "all" else list(library_map.keys())
            if len(target_ids) == 1:
                retrieved_chunks = VectorDatabaseService.search_similar_chunks(
                    user_id=user_id, document_id=target_ids[0], query_vector=query_vector, top_k=cls.TOP_K
                )
            else:
                retrieved_chunks = VectorDatabaseService.search_filtered_chunks(
                    user_id=user_id, document_ids=target_ids, query_vector=query_vector, top_k=cls.CROSS_DOC_TOP_K
                )
                if not retrieved_chunks:
                    retrieved_chunks = VectorDatabaseService.search_user_chunks(
                        user_id=user_id, query_vector=query_vector, top_k=cls.CROSS_DOC_TOP_K
                    )
        else:
            # No reference, no selection -> search all
            retrieved_chunks = VectorDatabaseService.search_user_chunks(
                user_id=user_id, query_vector=query_vector, top_k=cls.CROSS_DOC_TOP_K
            )
        # If still empty, honest fallback
        chat_history = cls.get_conversation_history(user_id, None, conversation_id)
        history_text = cls._format_chat_history(chat_history)
        if not retrieved_chunks:
            from app.services.ai.general_chat_service import GeneralChatService
            if not library_map:
                return await GeneralChatService.ask_question(
                    question, user_id, conversation_id
                )
            # Has uploads but nothing relevant -> pure general guidance (no retrieval loop)
            general = await GeneralChatService.ask_pure_general(
                question, user_id, conversation_id, save=False
            )
            answer_text = (
                "I couldn't find enough information about that in your uploaded documents.\n\n"
                f"Here is some general guidance that may help:\n\n{general.answer}"
            )
            result = RAGAnswerResponse(
                conversation_id=conversation_id,
                answer=answer_text,
                sources=[
                    SourceCitation(
                        document_id=s.document_id,
                        document_name=s.document_name,
                        page=s.page,
                        section=s.section,
                        snippet=s.snippet,
                    )
                    for s in general.sources
                ],
                confidence=general.confidence,
                followup_questions=general.followup_questions or [
                    "What are the main obligations in this contract?",
                    "When does this agreement terminate?",
                ],
            )
            cls._save_message_pair(user_id, None, conversation_id, question, result.answer, [s.model_dump() for s in result.sources])
            return result

        # Filter out chunks from non-indexed docs (if any)
        # Build context with per-document labels
        context_text = "\n\n".join([
            f"[Document: {cls._chunk_doc_name(c, user_id)}]\n"
            f"--- Snippet Page {c.get('page_number', 1)} • Section '{c.get('section', 'General')}' ---\n{c.get('text', '')}"
            for c in retrieved_chunks
        ])
        context_text = (
            f"{library_text}\n\n"
            "The excerpts below come from the user's document library. "
            "Attribute every claim to its labelled document; if the question names a document, prefer it.\n\n"
            + context_text
        )
        # Try Gemini cross-doc prompt (rotates keys on quota exhaustion)
        if gemini_key_manager.has_keys():
            for api_key in gemini_key_manager.iter_keys():
                try:
                    from google import genai
                    from google.genai import types
                    from app.services.ai.prompts import SYSTEM_CROSS_DOC_CHAT_PROMPT, CROSS_DOC_CHAT_USER_PROMPT_TEMPLATE
                    client = genai.Client(api_key=api_key)
                    prompt = CROSS_DOC_CHAT_USER_PROMPT_TEMPLATE.format(
                        user_question=question, chat_history_text=history_text, context_text=context_text
                    )
                    config = types.GenerateContentConfig(
                        system_instruction=SYSTEM_CROSS_DOC_CHAT_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.2,
                    )
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=settings.GEMINI_MODEL,
                        contents=prompt,
                        config=config
                    )
                    if response and response.text:
                        parsed = cls._parse_rag_json(response.text, conversation_id, retrieved_chunks)
                        if parsed:
                            gemini_key_manager.report_success(api_key)
                            parsed.sources = cls._attribute_sources(parsed.sources, retrieved_chunks, user_id)
                            cls._save_message_pair(
                                user_id, None, conversation_id, question,
                                parsed.answer, [s.model_dump() for s in parsed.sources],
                                referenced=list({c.get("document_id", "") for c in retrieved_chunks if c.get("document_id")}),
                            )
                            return parsed
                    break  # non-quota path done; fall through to fallback
                except Exception as e:
                    if gemini_key_manager.is_quota_error(e):
                        gemini_key_manager.report_quota_failure(api_key)
                        continue  # quota exhausted -> fail over to next key
                    logger.error(f"Gemini unified RAG error ({e}). Using grounded fallback.")
                    break

        # Fallback grounded answer, enriched with stored document intelligence
        # so library-wide chat stays factual without the live AI service.
        result = cls._generate_grounded_fallback_rag(question, retrieved_chunks, conversation_id)
        result.sources = cls._attribute_sources(result.sources, retrieved_chunks, user_id)
        top_doc = cls._chunk_doc_name(retrieved_chunks[0], user_id)
        # Prepend doc attribution for clarity when library-wide
        if len({c.get("document_id") for c in retrieved_chunks}) > 1:
            result.answer = f"Based on your document library (including '{top_doc}'):\n\n" + result.answer
        else:
            result.answer = f"Based on your uploaded document '{top_doc}':\n\n" + result.answer
        intel = cls._advisor_intel_block(
            user_id, [c.get("document_id", "") for c in retrieved_chunks if c.get("document_id")]
        )
        if intel and "informational assistance" in result.answer:
            result.answer = result.answer.replace(
                "*LegalLens provides informational assistance and does not replace professional legal advice.*",
                f"{intel.strip()}\n\n*LegalLens provides informational assistance and does not replace professional legal advice.*",
            )
        if cls._is_advice_question(question) and intel:
            result.followup_questions = [
                "What are the biggest risks across my documents?",
                "What should I check before signing?",
                "What questions should I ask a lawyer about this?",
            ]
        cls._save_message_pair(
            user_id, None, conversation_id, question,
            result.answer, [s.model_dump() for s in result.sources],
            referenced=list({c.get("document_id", "") for c in retrieved_chunks if c.get("document_id")}),
        )
        return result

    @classmethod
    def get_conversation_history(cls, user_id: str, document_id: Optional[str], conversation_id: Optional[str] = None) -> List[dict]:
        db = _load_db()
        convs = db.get("conversations", {})

        # Only consider conversations owned by this user. When document_id is
        # None (library-wide chat), all of the user's conversations qualify.
        owned = {
            c_id: data for c_id, data in convs.items()
            if data.get("user_id") == user_id
            and (document_id is None or data.get("document_id") == document_id)
        }
        if not owned:
            return []

        if conversation_id:
            match = owned.get(conversation_id)
            return match.get("messages", []) if match else []

        # No conversation_id provided: return the most recently updated conversation
        latest = max(owned.values(), key=lambda d: d.get("created_at", ""))
        return latest.get("messages", [])

    @classmethod
    def list_user_conversations(cls, user_id: str) -> List[dict]:
        """Lightweight chat list for the sidebar: id, preview, timestamps, referenced docs."""
        db = _load_db()
        convs = db.get("conversations", {})
        result = []
        for c_id, data in convs.items():
            if data.get("user_id") != user_id:
                continue
            messages = data.get("messages", [])
            preview = ""
            for m in reversed(messages):
                if m.get("role") == "user" and (m.get("content") or "").strip():
                    preview = m["content"][:80]
                    break
            result.append({
                "conversation_id": c_id,
                "document_id": data.get("document_id"),
                "preview": preview,
                "message_count": len(messages),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "referenced_document_ids": data.get("referenced_document_ids", []),
            })
        result.sort(key=lambda d: d.get("updated_at") or d.get("created_at", ""), reverse=True)
        return result

    @classmethod
    def _user_library_map(cls, user_id: str) -> dict:
        """Maps document_id -> display name for all user-owned documents."""
        try:
            from app.services.document_service import DocumentManager
            docs = DocumentManager.get_user_documents(user_id)
            return {d.id: d.name for d in docs if getattr(d, "id", "") and getattr(d, "name", "")}
        except Exception as e:
            logger.warning(f"Could not load user document library ({e}).")
            return {}

    @classmethod
    def _user_library_names(cls, user_id: str) -> List[str]:
        """Display names of all user-owned documents (for reference resolution)."""
        return list(cls._user_library_map(user_id).values())

    @classmethod
    def _chunk_doc_name(cls, chunk: dict, user_id: str) -> str:
        name = (chunk.get("document_name") or "").strip()
        if name:
            return name
        # Resolve via the live library (covers chunks indexed before name tagging).
        resolved = cls._user_library_map(user_id).get(chunk.get("document_id") or "")
        return resolved or chunk.get("document_id") or "uploaded document"

    @classmethod
    def _attribute_sources(
        cls, sources: List["SourceCitation"], chunks: List[dict], user_id: str
    ) -> List["SourceCitation"]:
        """Attaches document identity to each citation from the retrieved chunks."""
        by_page_doc: dict = {}
        for c in chunks:
            key = (c.get("document_id") or "", c.get("page_number", 1))
            by_page_doc.setdefault(key, c)
            # Also track by page alone so legacy citations keep working when
            # the chunk lacks a document_id.
            by_page_doc.setdefault(("__any__", c.get("page_number", 1)), c)
        enriched: List["SourceCitation"] = []
        for s in sources:
            chunk = by_page_doc.get((s.document_id, s.page))
            if not chunk:
                chunk = by_page_doc.get(("__any__", s.page), chunks[0] if chunks else {})
            s.document_id = chunk.get("document_id", "") or s.document_id or ""
            s.document_name = cls._chunk_doc_name(chunk, user_id)
            enriched.append(s)
        return enriched

    @classmethod
    def _advisor_intel_block(cls, user_id: str, document_ids: List[str]) -> str:
        """Grounded legal-advisor intel from stored document analyses.

        Gives the chatbot concrete, document-specific data (attention score,
        top risks, obligations, key dates) even when the live AI service is
        unreachable, so answers stay actual instead of generic.
        """
        try:
            from app.services.document_service import DocumentManager
        except Exception:
            return ""
        blocks: List[str] = []
        for doc_id in document_ids[:3]:
            try:
                entry = DocumentManager.get_document_by_id(doc_id, user_id)
                if not entry:
                    continue
                name = entry.get("metadata", {}).get("name", doc_id)
                analysis = DocumentManager.get_document_analysis(doc_id, user_id)
                if not analysis:
                    continue
                lines = [f"Document intelligence for '{name}':"]
                try:
                    lines.append(
                        f"- Attention score: {analysis.attention_score.score}/100 "
                        f"({analysis.attention_score.label})."
                    )
                except Exception:
                    pass
                for r in (analysis.potential_risks or [])[:3]:
                    lines.append(
                        f"- Risk ({r.severity}): {r.title} "
                        f"[Page {r.page}, {r.section}]."
                    )
                for ob in (analysis.obligations or [])[:3]:
                    lines.append(
                        f"- Obligation ({ob.party}): {ob.obligation[:120]} "
                        f"[Page {ob.page}, {ob.section}]."
                    )
                for kd in (analysis.key_dates or [])[:3]:
                    lines.append(
                        f"- Key date: {kd.event} — {kd.date_or_period} "
                        f"[Page {kd.page}, {kd.section}]."
                    )
                for p in (analysis.payments or [])[:2]:
                    lines.append(
                        f"- Payment: {p.item} — {p.amount} ({p.frequency}, due {p.due_date}) "
                        f"[Page {p.page}, {p.section}]."
                    )
                term = getattr(analysis, "termination_analysis", None)
                if term and getattr(term, "summary", "") and \
                        "no termination provision" not in term.summary.lower():
                    lines.append(
                        f"- Termination: {term.summary[:160]} "
                        f"[Page {term.page}, {term.section}]."
                    )
                if len(lines) > 1:
                    blocks.append("\n".join(lines))
            except Exception as e:
                logger.warning(f"Advisor intel skipped for {doc_id} ({e}).")
        if not blocks:
            return ""
        return (
            "\n\n--- LegalLens document intelligence (from your analysed uploads) ---\n"
            + "\n\n".join(blocks)
        )

    @classmethod
    def _is_small_talk(cls, question: str) -> bool:
        """Greetings, thanks, farewells, capability questions — no retrieval needed."""
        q = (question or "").strip().lower()
        if not q or len(q) > 120:
            return False
        patterns = (
            "hello", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "who are you", "what are you", "what can you do",
            "help me", "help", "thank", "thanks", "bye", "goodbye",
            "see you", "nice to meet",
        )
        if any(p in q for p in patterns):
            return True
        return q in (
            "hi", "hii", "hiii", "hey", "yo", "sup", "hello", "hai", "hola",
            "hlo", "hlw", "helo", "hiya", "ok", "okay", "cool", "great", "nice"
        )

    @classmethod
    def _small_talk_reply(
        cls, question: str, conversation_id: str, context_name: Optional[str] = None
    ) -> RAGAnswerResponse:
        """Friendly conversational reply that also teaches chatbot capabilities."""
        q = (question or "").strip().lower()
        if any(p in q for p in ("thank", "thanks")):
            answer = (
                "You're welcome! If you have more questions — about your documents "
                "or general legal topics — just ask."
            )
        elif any(p in q for p in ("bye", "goodbye", "see you")):
            answer = "Goodbye! Your documents and chat history are saved here whenever you need them."
        elif any(p in q for p in ("who are you", "what are you", "what can you do", "help")):
            answer = (
                "I'm LegalLens AI — your legal document assistant. I can:\n\n"
                "• Read your uploaded contracts and explain them in plain language\n"
                "• Answer questions with exact page and section citations\n"
                "• Flag risks, obligations, payments, deadlines and renewal traps\n"
                "• Compare two contracts side by side\n"
                "• Answer general legal questions even with no document uploaded\n\n"
                "Upload a contract to begin, or just ask me a legal question."
            )
        elif any(p in q for p in ("how are you",)):
            answer = (
                "I'm running well and ready to help! Ask me about one of your "
                "uploaded documents, or any general legal question."
            )
        else:
            doc_hint = (
                f" I can see you have '{context_name}' selected — ask me anything about it,"
                " or request a complete analysis."
                if context_name else
                " Upload a contract and I'll explain it in plain language — or just ask me "
                "any general legal question right away."
            )
            answer = (
                f"Hello! I'm LegalLens AI, your legal document assistant.{doc_hint}"
            )
        return RAGAnswerResponse(
            conversation_id=conversation_id,
            answer=f"{answer}\n\n*LegalLens provides informational assistance and does not replace professional legal advice.*",
            sources=[],
            confidence="high",
            followup_questions=[
                "What should I check before signing a contract?",
                "What is a non-compete clause?",
                "How do I upload and analyse a document?",
            ],
        )

    @classmethod
    def _is_advice_question(cls, question: str) -> bool:
        q = question.lower()
        return any(
            phrase in q
            for phrase in (
                "should i sign", "should i agree", "is this fair", "is it safe",
                "what should i do", "do you recommend", "is this risky",
                "should i be worried", "can i negotiate", "what should i check",
                "before signing", "before i sign", "red flag", "dealbreaker",
                "deal breaker",
            )
        )

    @classmethod
    def delete_conversation_history(cls, user_id: str, document_id: str) -> bool:
        db = _load_db()
        convs = db.get("conversations", {})
        keys_to_del = [
            c_id for c_id, data in convs.items()
            if data.get("user_id") == user_id and data.get("document_id") == document_id
        ]
        for k in keys_to_del:
            del convs[k]
        db["conversations"] = convs
        _save_db(db)
        return True

    @classmethod
    def _save_message_pair(cls, user_id: str, document_id: Optional[str], conversation_id: str, question: str, answer: str, sources: list, referenced: Optional[List[str]] = None):
        db = _load_db()
        if "conversations" not in db:
            db["conversations"] = {}

        # Prevent hijacking another user's conversation by ID
        existing = db["conversations"].get(conversation_id)
        if existing and (existing.get("user_id") != user_id or existing.get("document_id") != document_id):
            raise ValueError("Conversation is not associated with this user/document.")

        conv_entry = db["conversations"].get(conversation_id, {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "document_id": document_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "messages": [],
            "referenced_document_ids": [],
        })

        ts = time.strftime("%H:%M", time.localtime())
        conv_entry["messages"].append({"role": "user", "content": question, "created_at": ts})
        conv_entry["messages"].append({"role": "assistant", "content": answer, "sources": sources, "created_at": ts})
        conv_entry["updated_at"] = ts
        # Track every document this chat has drawn on (useful context, not ownership).
        known = set(conv_entry.get("referenced_document_ids") or [])
        for doc_id in referenced or []:
            if doc_id:
                known.add(doc_id)
        if document_id:
            known.add(document_id)
        conv_entry["referenced_document_ids"] = sorted(known)

        db["conversations"][conversation_id] = conv_entry
        _save_db(db)

    @classmethod
    def _format_chat_history(cls, messages: List[dict]) -> str:
        if not messages:
            return "No previous conversation."
        lines = []
        for msg in messages[-10:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {msg.get('content')}")
        return "\n".join(lines)

    @classmethod
    def _expand_query_with_history(cls, question: str, history: List[dict]) -> str:
        """Enriches short or pronoun-heavy follow-up questions with context from recent turns."""
        q = (question or "").strip()
        words = q.split()
        pronouns = {"it", "this", "that", "they", "them", "these", "those", "clause", "section", "what about", "how about"}
        has_pronoun = any(p in q.lower() for p in pronouns)
        
        if (len(words) <= 5 or has_pronoun) and history:
            recent_user_questions = [
                m.get("content", "") for m in history[-6:]
                if m.get("role") == "user" and m.get("content")
            ]
            if recent_user_questions:
                last_q = recent_user_questions[-1]
                # Filter out small talk from context
                if not cls._is_small_talk(last_q):
                    return f"{last_q} {q}"
        return q

    @classmethod
    def _parse_rag_json(cls, text: str, conversation_id: str, retrieved_chunks: list) -> Optional[RAGAnswerResponse]:
        try:
            data = json.loads(text)
            raw_sources = data.get("sources", [])
            sources = []
            if isinstance(raw_sources, list):
                for s in raw_sources:
                    if isinstance(s, dict):
                        sources.append(SourceCitation(
                            page=int(s.get("page", 1)) if str(s.get("page", 1)).isdigit() else 1,
                            section=str(s.get("section", "General")),
                            clause_id=str(s.get("clause_id", "")),
                            snippet=str(s.get("snippet", ""))
                        ))
            if not sources and retrieved_chunks:
                top = retrieved_chunks[0]
                sources.append(SourceCitation(
                    page=top.get("page_number", 1),
                    section=top.get("section", "General"),
                    clause_id=top.get("clause_id", ""),
                    snippet=top.get("text", "")[:120]
                ))
            return RAGAnswerResponse(
                conversation_id=conversation_id,
                answer=data.get("answer", ""),
                sources=sources,
                confidence=data.get("confidence", "high"),
                followup_questions=data.get("followup_questions", [])
            )
        except Exception as e:
            logger.warning(f"RAG JSON parse error ({e}). Using regex recovery...")
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    raw_sources = data.get("sources", [])
                    sources = []
                    if isinstance(raw_sources, list):
                        for s in raw_sources:
                            if isinstance(s, dict):
                                sources.append(SourceCitation(
                                    page=int(s.get("page", 1)) if str(s.get("page", 1)).isdigit() else 1,
                                    section=str(s.get("section", "General")),
                                    clause_id=str(s.get("clause_id", "")),
                                    snippet=str(s.get("snippet", ""))
                                ))
                    return RAGAnswerResponse(
                        conversation_id=conversation_id,
                        answer=data.get("answer", ""),
                        sources=sources,
                        confidence=data.get("confidence", "medium"),
                        followup_questions=data.get("followup_questions", [])
                    )
                except Exception:
                    pass
        return None


    @classmethod
    def _generate_grounded_fallback_rag(cls, question: str, retrieved_chunks: list, conversation_id: str) -> RAGAnswerResponse:
        """
        Honest offline fallback. Rather than fabricating legal claims about
        the document, it surfaces the actual retrieved text excerpt as a
        direct quote so the user can read the real source content.
        """
        if not retrieved_chunks:
            return RAGAnswerResponse(
                conversation_id=conversation_id,
                answer=(
                    "I couldn't find enough information about that in the uploaded document.\n\n"
                    "*LegalLens provides informational assistance and does not replace professional legal advice.*"
                ),
                sources=[],
                confidence="low",
                followup_questions=["What are the main obligations in this contract?", "When does this agreement terminate?"]
            )

        sources: List[SourceCitation] = []
        seen_keys = set()
        for c in retrieved_chunks[:4]:
            key = (c.get("document_id", ""), c.get("page_number", 1))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            sources.append(SourceCitation(
                page=c.get("page_number", 1),
                section=c.get("section", "General"),
                clause_id=c.get("clause_id", ""),
                snippet=(c.get("text") or "")[:160],
                document_id=c.get("document_id", ""),
                document_name=c.get("document_name", "") or c.get("document_id", ""),
            ))

        top = retrieved_chunks[0]
        page_num = top.get("page_number", 1)
        sec_title = top.get("section", "General")

        # Harvest query-relevant sentences across the top chunks so the answer
        # carries real data from several parts of the document, not one snippet.
        q_terms = [w.lower() for w in question.split() if len(w) > 3]
        quotes: List[str] = []
        for chunk in retrieved_chunks[:3]:
            chunk_text = (chunk.get("text") or "").strip()
            if not chunk_text:
                continue
            sentences = re.split(r'(?<=[.!?])\s+', chunk_text)
            relevant = [s.strip() for s in sentences if any(t in s.lower() for t in q_terms)]
            picked = (relevant[:2] if relevant else sentences[:1])
            for sentence in picked:
                sentence = re.sub(r'\s+', ' ', sentence).strip(" .")
                if sentence and sentence not in quotes:
                    label = ""
                    if chunk is not top:
                        c_doc = (chunk.get("document_name") or chunk.get("document_id") or "").strip()
                        label = (
                            f" (Page {chunk.get('page_number', 1)}, "
                            f"Section '{chunk.get('section', 'General')}'"
                            f"{f', {c_doc}' if c_doc else ''})"
                        )
                    quotes.append(f"> {sentence[:280]}.{label}")
                if len(quotes) >= 3:
                    break
            if len(quotes) >= 3:
                break

        quote_block = "\n".join(quotes[:3]) if quotes else "> (No directly matching sentence found.)"

        answer = (
            f"Here is the most relevant text found in your document (Page {page_num}, Section '{sec_title}'):\n\n"
            f"{quote_block}\n\n"
            "The above are direct excerpts from the document. "
            "To receive a plain-language interpretation, connect the live Gemini AI service.\n\n"
            "*LegalLens provides informational assistance and does not replace professional legal advice.*"
        )

        return RAGAnswerResponse(
            conversation_id=conversation_id,
            answer=answer,
            sources=sources,
            confidence="medium",
            followup_questions=[
                f"What else does the \"{sec_title}\" section state?",
                "Are there any other related clauses in the document?",
            ]
        )

import asyncio
import json
import time
import re
from typing import Optional
from app.config import settings
from app.core.logging import logger
from app.models.document import ExtractedDocument
from app.services.ai.schemas import (
    FullDocumentAnalysis, 
    ExecutiveSummary, 
    ImportantClause, 
    PotentialRisk, 
    ObligationItem, 
    KeyDateItem, 
    PaymentDetails, 
    TerminationAnalysis, 
    RenewalAnalysis, 
    LawyerQuestionItem, 
    AttentionScoreDetails
)
from app.services.ai.prompts import SYSTEM_LEGAL_ANALYSIS_PROMPT, ANALYSIS_USER_PROMPT_TEMPLATE

class GeminiAnalysisService:
    """
    Phase 3: Dedicated Gemini Legal Document Intelligence Service Layer.
    Executes structured legal analysis via Google Gemini API server-side.
    Validates with Pydantic and applies fallback recovery if needed.
    """

    @classmethod
    async def analyze_document(cls, extracted_doc: ExtractedDocument, user_id: str) -> FullDocumentAnalysis:
        from app.services.ai.gemini_keys import gemini_key_manager

        # Check if real API keys are configured (rotates on quota exhaustion)
        if gemini_key_manager.has_keys():
            for api_key in gemini_key_manager.iter_keys():
                try:
                    logger.info(f"Invoking Gemini API ({settings.GEMINI_MODEL}) for document {extracted_doc.document_id}...")
                    analysis = await cls._call_gemini_api(extracted_doc, user_id, api_key)
                    if analysis:
                        gemini_key_manager.report_success(api_key)
                        logger.info(f"Gemini API document analysis successfully generated and validated for {extracted_doc.document_id}.")
                        return analysis
                    # Empty/soft failure: try the next key before falling back.
                    logger.warning("Gemini API returned no usable analysis; trying next key if available.")
                except Exception as e:
                    if gemini_key_manager.is_quota_error(e):
                        gemini_key_manager.report_quota_failure(api_key)
                        continue  # quota exhausted -> fail over to next key
                    logger.error(f"Gemini API call or validation failed, using grounded fallback analysis engine: {e}")
                    break
            else:
                # for/else runs only when the loop never hit break/return,
                # i.e. every key was tried without success.
                logger.error("All Gemini API keys exhausted or failed; using grounded fallback analysis engine.")
        else:
            logger.info("No active GEMINI_API_KEY configured. Utilizing grounded AI analysis engine.")

        return cls._generate_grounded_fallback_analysis(extracted_doc, user_id)

    @classmethod
    async def _call_gemini_api(cls, extracted_doc: ExtractedDocument, user_id: str, api_key: str) -> Optional[FullDocumentAnalysis]:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
                document_id=extracted_doc.document_id,
                filename=extracted_doc.filename,
                total_pages=extracted_doc.total_pages,
                extracted_text=extracted_doc.full_text[:60000]  # Increased from 35K — Gemini Flash supports 1M+ tokens
            )

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_LEGAL_ANALYSIS_PROMPT,
                response_mime_type="application/json",
                response_schema=FullDocumentAnalysis,
                temperature=0.1,
            )

            # Wrap the synchronous Gemini SDK call in asyncio.to_thread
            # so it doesn't block the FastAPI event loop.
            def _sync_generate():
                return client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=config,
                )

            response = await asyncio.to_thread(_sync_generate)

            if response and response.text:
                return cls._parse_and_validate_json(response.text, extracted_doc, user_id)
        except Exception as e:
            # Retryable errors (503/429) bubble up so caller can failover to next key
            from app.services.ai.gemini_keys import gemini_key_manager as _gkm
            if _gkm.is_retryable_error(e):
                raise
            logger.error(f"Error during Gemini SDK invocation/validation: {e}")
            return None

    @classmethod
    def _parse_and_validate_json(cls, text: str, extracted_doc: ExtractedDocument, user_id: str) -> Optional[FullDocumentAnalysis]:
        # Attempt direct JSON load
        try:
            json_data = json.loads(text)
            json_data["document_id"] = extracted_doc.document_id
            json_data["user_id"] = user_id
            if "created_at" not in json_data or not json_data["created_at"]:
                json_data["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return FullDocumentAnalysis.model_validate(json_data)
        except Exception as first_err:
            logger.warning(f"Direct JSON parse failed ({first_err}). Attempting regex recovery...")
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    json_data = json.loads(match.group(0))
                    json_data["document_id"] = extracted_doc.document_id
                    json_data["user_id"] = user_id
                    if "created_at" not in json_data or not json_data["created_at"]:
                        json_data["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    return FullDocumentAnalysis.model_validate(json_data)
                except Exception as second_err:
                    logger.error(f"JSON regex recovery also failed: {second_err}")
        return None

    @classmethod
    def _compute_attention_score(cls, risks: list) -> AttentionScoreDetails:
        """
        Derives a transparent document Attention Score (0-100) based on identified risk count & severity.
        Labelled cleanly as an AI document attention indicator, not a legal rating.
        """
        high_count = sum(1 for r in risks if getattr(r, 'severity', '') == 'high')
        med_count = sum(1 for r in risks if getattr(r, 'severity', '') == 'medium')
        low_count = sum(1 for r in risks if getattr(r, 'severity', '') == 'low')

        raw_score = 35 + (high_count * 25) + (med_count * 12) + (low_count * 5)
        score = min(98, max(20, raw_score))

        if score >= 80:
            label = "Requires Immediate Attention"
        elif score >= 60:
            label = "Requires Review"
        else:
            label = "Standard Terms"

        reasoning = (
            f"Derived Attention Score ({score}/100) reflects {high_count} high-severity risk(s), "
            f"{med_count} medium-severity risk(s), and {low_count} low-severity item(s) flagged by LegalLens AI."
        )

        return AttentionScoreDetails(score=score, label=label, reasoning=reasoning)

    @classmethod
    def _generate_grounded_fallback_analysis(cls, extracted_doc: ExtractedDocument, user_id: str) -> FullDocumentAnalysis:
        """
        Honest, document-grounded fallback analysis used when the Gemini API is
        unavailable. Every finding is derived from the ACTUAL extracted document
        content — no invented dollar amounts, deadlines, or citations. Categories
        that cannot be grounded in the document are reported as not identified.
        """
        document_text = extracted_doc.full_text
        lowered_terms = document_text.lower()
        max_page = max(1, extracted_doc.total_pages)
        filename_lower = extracted_doc.filename.lower()

        def _page_for(text_snippet: str) -> int:
            """Find the actual page containing the snippet text."""
            for p in extracted_doc.pages:
                if text_snippet in p.text:
                    return p.page_number
            return 1

        def _section_for(page_num: int) -> str:
            for s in extracted_doc.sections:
                if s.start_page <= page_num <= s.end_page:
                    return s.title
            return "General"

        # 1. Executive Summary (grounded in actual extraction statistics)
        section_titles = [s.title for s in extracted_doc.sections[:5]] or ["General Terms"]
        key_points = []
        if extracted_doc.clauses:
            key_points.append(f"Extraction identified {len(extracted_doc.clauses)} numbered clause(s) in the document.")
        if extracted_doc.sections:
            key_points.append(f"Detected section headings: {', '.join(section_titles[:4])}")
        if "lease" in filename_lower or "rental" in filename_lower:
            doc_type = "lease / rental agreement"
        elif "employment" in filename_lower or "offer" in filename_lower:
            doc_type = "employment / offer agreement"
        elif filename_lower.endswith((".md", ".markdown")):
            doc_type = "markdown document"
        elif filename_lower.endswith(".csv"):
            doc_type = "data / spreadsheet export"
        elif filename_lower.endswith((".html", ".htm")):
            doc_type = "web document"
        elif filename_lower.endswith(".log"):
            doc_type = "log file"
        elif any(k in filename_lower for k in ("invoice", "receipt", "bill")):
            doc_type = "invoice / billing document"
        elif any(k in lowered_terms for k in ("contract", "agreement", "policy", "terms", "clause", "hereby", "whereas")):
            doc_type = "contract / agreement"
        else:
            doc_type = "document"
        summary_text = (
            f"'{extracted_doc.filename}' is a {doc_type} spanning {max_page} page(s). "
            f"The automatic (offline) analysis identified its structure but did not fabricate legal judgements. "
            f"Connect the Gemini API for a fully grounded clause-by-clause review."
        )
        if not key_points:
            key_points.append(f"Document contains {max_page} page(s) and {len(extracted_doc.sections)} detected section(s).")

        # 2. Important Clauses (from ACTUAL detected clauses/sections only)
        clauses = []
        for c in extracted_doc.clauses[:12]:
            clauses.append(ImportantClause(
                clause_id=c.clause_id or "",
                title=c.title or c.text[:40],
                summary=c.text[:200] if c.text else "Clause text not available.",
                importance="medium",
                page=c.page,
                section=c.section if c.section else "General",
                source_text=c.text[:300] or "",
            ))
        if not clauses:
            for s in extracted_doc.sections[:8]:
                clauses.append(ImportantClause(
                    clause_id="",
                    title=s.title,
                    summary=s.title,
                    importance="medium",
                    page=s.start_page,
                    section=s.title,
                    source_text="",
                ))

        # 3. Potential Risks (only when a risk-relevant section is actually present)
        risk_keywords = [
            "terminat", "penalt", "liab", "non-compet", "liquidated",
            "clawback", "indemnif", "confidential", "renew", "forfeit",
            "waiver", "damage", "breach", "covenant", "restriction",
        ]
        risks = []
        seen_risk = set()
        for c in extracted_doc.clauses[:12]:
            title_lower = (c.title or c.text or "").lower()
            if any(k in title_lower for k in risk_keywords):
                if c.title in seen_risk:
                    continue
                seen_risk.add(c.title)
                risks.append(PotentialRisk(
                    title=f"{c.title} — review required",
                    category="Document provision",
                    severity="medium",
                    explanation=(
                        f"The clause \"{c.title}\" appears to involve terms that may carry obligations or consequences. "
                        "Consider reviewing this provision carefully before signing."
                    ),
                    why_it_matters="This provision may affect your rights or obligations, so it deserves careful attention.",
                    page=c.page,
                    section=c.section if c.section else "General",
                    clause_id=c.clause_id or "",
                    source_text=c.text[:200] or "",
                    suggested_question=f"What does the \"{c.title}\" provision require of each party?",
                    confidence="medium",
                ))

        # 4. Obligations (only when the actual text contains duty language)
        obligation_keywords = ["shall", "must", "will provide", "agree to", "responsible for", "obligat"]
        obligations = []
        seen_obligation = set()

        def _add_obligation(party: str, text: str, page_num: int, section: str):
            key = (text or "")[:80]
            if not text or key in seen_obligation or len(obligations) >= 8:
                return
            seen_obligation.add(key)
            obligations.append(ObligationItem(
                party=party,
                obligation=text.strip()[:200],
                deadline="As specified in document",
                consequence="As specified in document",
                page=page_num,
                section=section or "General",
            ))

        for c in extracted_doc.clauses[:10]:
            text_lower = (c.text or "").lower()
            if any(k in text_lower for k in obligation_keywords):
                _add_obligation(
                    "" if "lease" not in filename_lower else "Tenant",
                    (c.text[:200] if c.text else (c.title or "Obligation")), c.page,
                    c.section if c.section else "General",
                )

        # When no numbered clauses exist, scan real page sentences for duty language.
        if not obligations:
            page_texts_all = {p.page_number: p.text for p in extracted_doc.pages}
            duty_pattern = re.compile(
                r'([^.\n]{10,220}?\b(?:shall|must|agree to|responsible for|is obligated to)\b[^.\n]{0,160}\.)',
                re.IGNORECASE,
            )
            for page_num, page_text in sorted(page_texts_all.items()):
                for m in duty_pattern.finditer(page_text):
                    sentence = re.sub(r'\s+', ' ', m.group(1)).strip()
                    _add_obligation(
                        "" if "lease" not in filename_lower else "Tenant",
                        sentence, page_num, _section_for(page_num),
                    )
                if len(obligations) >= 8:
                    break

        # 5. Key Dates (regex-detected periods actually present in the text)
        key_dates = []
        period_patterns = re.compile(
            r'(within|at least|not less than|prior to|no earlier than|no later than)?\s*'
            r'(\d{1,3}\s*(?:day|month|week|year)s?)\b',
            re.IGNORECASE
        )
        page_texts = {p.page_number: p.text for p in extracted_doc.pages}
        seen_dates = set()
        for page_num, page_text in sorted(page_texts.items()):
            for m in period_patterns.finditer(page_text):
                period = m.group(0).strip()
                if period.lower() in seen_dates:
                    continue
                seen_dates.add(period.lower())
                context = page_text[max(0, m.start() - 80):m.start() + 40].replace("\n", " ").strip()
                key_dates.append(KeyDateItem(
                    event=f"Time-based requirement ({period})",
                    date_or_period=period,
                    importance="medium",
                    page=page_num,
                    section=_section_for(page_num),
                ))

        # 6. Payments (only ACTUAL dollar amounts found in the document)
        payments = []
        amount_pattern = re.compile(r'(\$\s?\d[\d,]*[,.]?\d{0,2})')
        seen_payment = set()
        for page_num, page_text in sorted(page_texts.items()):
            for m in amount_pattern.finditer(page_text):
                amount = m.group(1).strip()
                if amount in seen_payment:
                    continue
                seen_payment.add(amount)
                context_line = page_text[:page_text.find(amount)].split("\n")[-1]
                payments.append(PaymentDetails(
                    item=context_line.strip()[:60] or "Payment (amount recovered from text)",
                    amount=amount,
                    frequency="Not specified",
                    due_date="Not specified",
                    late_fees="Not specified",
                    deposits="Not specified",
                    refund_conditions="Not specified",
                    additional_charges="Not specified",
                    page=page_num,
                    section=_section_for(page_num),
                ))

        # 7. Termination (grounded in actual text or reported as not identified)
        termination_text = next(
            (c.text for c in extracted_doc.clauses if "terminat" in (c.title or "").lower() or "terminat" in (c.text or "").lower()),
            None
        )
        if termination_text:
            term_page = _page_for(termination_text[:80])
            termination = TerminationAnalysis(
                who_can_terminate="Not explicitly parsed without live AI",
                conditions="Referenced in the document's termination provision.",
                notice_period="As specified in document",
                early_termination="Referenced in the document.",
                penalties="As specified in document",
                consequences="As specified in document",
                cure_period="Not identified",
                summary="Termination terms were auto-detected in the document text. Review the quoted clause in full.",
                page=term_page,
                section=_section_for(term_page),
            )
        else:
            termination = TerminationAnalysis(
                who_can_terminate="Not identified",
                conditions="No termination provision was identified in the extracted text.",
                notice_period="Not identified",
                early_termination="Not identified",
                penalties="Not identified",
                consequences="Not identified",
                cure_period="Not identified",
                summary="No termination provision was identified in the document.",
                page=1,
                section="Termination",
            )

        # 8. Renewal (grounded or reported as not identified)
        renewal_text = next(
            (c.text for c in extracted_doc.clauses if "renew" in (c.title or "").lower() or "renew" in (c.text or "").lower()),
            None
        )
        if renewal_text:
            renew_page = _page_for(renewal_text[:80])
            renewal = RenewalAnalysis(
                has_renewal=True,
                automatic_renewal="automatic" in renewal_text.lower() or "automatically" in renewal_text.lower(),
                renewal_period="As specified in document",
                notice_period="As specified in document",
                opt_out="See clause text",
                consequences="As specified in document",
                summary="Renewal terms were auto-detected in the document text. Review the quoted clause in full.",
                page=renew_page,
                section=_section_for(renew_page),
            )
        else:
            renewal = RenewalAnalysis(
                has_renewal=False,
                automatic_renewal=False,
                renewal_period="N/A",
                notice_period="N/A",
                opt_out="N/A",
                consequences="N/A",
                summary="No renewal provision was identified in the document.",
                page=1,
                section="Renewal",
            )

        # 9. Lawyer Questions (only referencing actual detected provisions)
        lawyer_questions = []
        for r in risks[:5]:
            lawyer_questions.append(LawyerQuestionItem(
                question=r.suggested_question or f"Please review the \"{r.title}\" provision.",
                context="This question was auto-generated from a provision detected in the document text.",
                page=r.page,
                section=r.section,
            ))
        if not lawyer_questions:
            lawyer_questions.append(LawyerQuestionItem(
                question="Which provisions in this document carry the most significant obligations or risks?",
                context="No specific high-attention clause was detected automatically; a human review is recommended.",
                page=1,
                section="General",
            ))

        # 10. Attention Score (derived ONLY from the real risk items above)
        attention_score = cls._compute_attention_score(risks)

        return FullDocumentAnalysis(
            document_id=extracted_doc.document_id,
            user_id=user_id,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            attention_score=attention_score,
            executive_summary=ExecutiveSummary(summary=summary_text, key_points=key_points),
            important_clauses=clauses,
            potential_risks=risks,
            obligations=obligations,
            key_dates=key_dates,
            payments=payments,
            termination_analysis=termination,
            renewal_analysis=renewal,
            lawyer_questions=lawyer_questions,
            disclaimer="LegalLens provides informational assistance and does not replace professional legal advice."
        )


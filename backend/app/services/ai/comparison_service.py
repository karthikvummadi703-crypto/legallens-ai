import json
import re
from typing import List, Optional
from app.config import settings
from app.core.logging import logger
from app.services.ai.schemas import (
    DocumentComparison,
    ComparisonDifference,
    ComparisonSummary,
)
from app.services.ai.prompts import SYSTEM_COMPARISON_PROMPT, COMPARISON_USER_PROMPT_TEMPLATE

DISCLAIMER = "LegalLens provides informational assistance and does not replace professional legal advice."
_MAX_DIFFERENCES = 12


def _normalize(text: str) -> str:
    return re.sub(r'[^a-z0-9 ]', '', (text or '').lower()).strip()


def _category_for(section: str, title: str) -> str:
    haystack = f"{section} {title}".lower()
    for keyword, category in [
        ("terminat", "Termination"),
        ("payment", "Payment"),
        ("compensat", "Payment"),
        ("salary", "Payment"),
        ("bonus", "Payment"),
        ("liab", "Liability"),
        ("indemnif", "Liability"),
        ("renew", "Renewal"),
        ("confidential", "Confidentiality"),
        ("non-compete", "Restrictive Covenants"),
        ("non-competit", "Restrictive Covenants"),
        ("arbitrat", "Dispute Resolution"),
        ("dispute", "Dispute Resolution"),
    ]:
        if keyword in haystack:
            return category
    return "General"


class ComparisonService:
    """
    Contract comparison engine: contrasts two user-owned documents clause by
    clause and reports Added / Removed / Changed / Unchanged differences with
    plain-language, grounded explanations.
    """

    @classmethod
    async def compare_documents(cls, user_id: str, doc_a_id: str, doc_b_id: str) -> DocumentComparison:
        # Local import avoids a circular dependency with document_service.
        from app.services.document_service import DocumentManager

        if doc_a_id == doc_b_id:
            raise ValueError("Please select two different documents to compare.")

        entry_a = DocumentManager.get_document_by_id(doc_a_id, user_id)
        entry_b = DocumentManager.get_document_by_id(doc_b_id, user_id)
        if not entry_a or not entry_b:
            raise ValueError("One or both documents were not found or access was denied.")

        name_a = entry_a.get("metadata", {}).get("name", "Document A")
        name_b = entry_b.get("metadata", {}).get("name", "Document B")

        analysis_a = DocumentManager.get_document_analysis(doc_a_id, user_id)
        analysis_b = DocumentManager.get_document_analysis(doc_b_id, user_id)

        from app.services.ai.gemini_keys import gemini_key_manager

        if gemini_key_manager.has_keys():
            for api_key in gemini_key_manager.iter_keys():
                try:
                    result = await cls._call_gemini_api(
                        user_id, doc_a_id, name_a, entry_a, analysis_a,
                        doc_b_id, name_b, entry_b, analysis_b, api_key,
                    )
                    if result:
                        gemini_key_manager.report_success(api_key)
                        logger.info(f"Gemini comparison generated for '{doc_a_id}' vs '{doc_b_id}'.")
                        return result
                    logger.warning("Gemini comparison returned no result; trying next key if available.")
                except Exception as e:
                    if gemini_key_manager.is_quota_error(e):
                        gemini_key_manager.report_quota_failure(api_key)
                        continue  # quota exhausted -> fail over to next key
                    logger.error(f"Gemini comparison failed ({e}). Using grounded fallback comparison.")
                    break
            else:
                logger.error("All Gemini API keys exhausted for comparison; using grounded fallback comparison.")

        return cls._grounded_fallback_compare(
            doc_a_id, name_a, entry_a, analysis_a,
            doc_b_id, name_b, entry_b, analysis_b,
        )

    # ------------------------------------------------------------------
    # Gemini path
    # ------------------------------------------------------------------
    @classmethod
    def _clause_digest(cls, entry: dict, analysis) -> str:
        lines: List[str] = []
        if analysis and getattr(analysis, "important_clauses", None):
            for c in analysis.important_clauses:
                lines.append(
                    f"- [{c.section} | Page {c.page}] {c.title}: {c.summary}"
                )
            if getattr(analysis, "payments", None):
                for p in analysis.payments:
                    lines.append(f"- [Payment | Page {p.page}] {p.item}: {p.amount} ({p.frequency}, due {p.due_date})")
            if getattr(analysis, "obligations", None):
                for ob in analysis.obligations:
                    lines.append(f"- [Obligation | Page {ob.page}] {ob.party}: {ob.obligation} (deadline: {ob.deadline})")
        else:
            extracted = entry.get("extracted", {})
            for c in (extracted.get("clauses") or [])[:20]:
                title = c.get("title") or (c.get("text") or "")[:60]
                lines.append(f"- [{c.get('section', 'General')} | Page {c.get('page', 1)}] {title}: {(c.get('text') or '')[:220]}")
            if not lines:
                for s in (extracted.get("sections") or [])[:10]:
                    lines.append(f"- [{s.get('title', 'General')}] Section present (pages {s.get('start_page', 1)}-{s.get('end_page', 1)})")
        return "\n".join(lines) if lines else "(No clause structure could be extracted from this document.)"

    @classmethod
    async def _call_gemini_api(
        cls, user_id: str,
        doc_a_id: str, name_a: str, entry_a: dict, analysis_a,
        doc_b_id: str, name_b: str, entry_b: dict, analysis_b,
        api_key: str,
    ) -> Optional[DocumentComparison]:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            prompt = COMPARISON_USER_PROMPT_TEMPLATE.format(
                doc_a_name=name_a,
                doc_a_id=doc_a_id,
                doc_a_clauses=cls._clause_digest(entry_a, analysis_a)[:12000],
                doc_b_name=name_b,
                doc_b_id=doc_b_id,
                doc_b_clauses=cls._clause_digest(entry_b, analysis_b)[:12000],
            )
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_COMPARISON_PROMPT,
                response_mime_type="application/json",
                response_schema=DocumentComparison,
                temperature=0.1,
            )
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            if response and response.text:
                data = json.loads(response.text)
                data["document_a_id"] = doc_a_id
                data["document_b_id"] = doc_b_id
                data["document_a_name"] = name_a
                data["document_b_name"] = name_b
                data["disclaimer"] = DISCLAIMER
                return DocumentComparison.model_validate(data)
        except Exception as e:
            logger.error(f"Error during Gemini comparison invocation/validation: {e}")
            return None
        return None

    # ------------------------------------------------------------------
    # Honest deterministic fallback (no invented wording)
    # ------------------------------------------------------------------
    @classmethod
    def _grounded_fallback_compare(
        cls, doc_a_id: str, name_a: str, entry_a: dict, analysis_a,
        doc_b_id: str, name_b: str, entry_b: dict, analysis_b,
    ) -> DocumentComparison:
        clauses_a = list(getattr(analysis_a, "important_clauses", None) or []) if analysis_a else []
        clauses_b = list(getattr(analysis_b, "important_clauses", None) or []) if analysis_b else []

        # Fall back to raw extracted sections when a document was never analyzed.
        if not clauses_a:
            clauses_a = cls._sections_as_clauses(entry_a)
        if not clauses_b:
            clauses_b = cls._sections_as_clauses(entry_b)

        index_b = {_normalize(c.title if hasattr(c, "title") else c.get("title", "")): c for c in clauses_b}
        matched_b = set()
        differences: List[ComparisonDifference] = []

        def _title(c) -> str:
            return c.title if hasattr(c, "title") else c.get("title", "Untitled provision")

        def _summary(c) -> str:
            return (c.summary if hasattr(c, "summary") else c.get("text", "")) or ""

        def _section(c) -> str:
            return (c.section if hasattr(c, "section") else c.get("section", "")) or "General"

        def _page(c) -> int:
            try:
                return int(c.page if hasattr(c, "page") else c.get("page", 1))
            except Exception:
                return 1

        for c_a in clauses_a:
            key = _normalize(_title(c_a))
            c_b = index_b.get(key)
            if c_b is None:
                differences.append(ComparisonDifference(
                    clause_title=_title(c_a),
                    contract_a=f"Present in '{name_a}' ({_section(c_a)}, Page {_page(c_a)}): {_summary(c_a)[:220]}",
                    contract_b=f"No matching provision was identified in '{name_b}'.",
                    difference_type="Removed",
                    attention_level="medium",
                    category=_category_for(_section(c_a), _title(c_a)),
                    ai_explanation=(
                        f"This topic appears in '{name_a}' but was not identified in '{name_b}'. "
                        "Consider reviewing whether the protection or obligation it describes still applies to you."
                    ),
                ))
            else:
                matched_b.add(key)
                if _normalize(_summary(c_a)) == _normalize(_summary(c_b)):
                    if len([d for d in differences if d.difference_type == "Unchanged"]) < 2:
                        differences.append(ComparisonDifference(
                            clause_title=_title(c_a),
                            contract_a=_summary(c_a)[:220],
                            contract_b=_summary(c_b)[:220],
                            difference_type="Unchanged",
                            attention_level="informational",
                            category=_category_for(_section(c_a), _title(c_a)),
                            ai_explanation="This provision reads the same in both documents.",
                        ))
                else:
                    cat = _category_for(_section(c_a), _title(c_a))
                    differences.append(ComparisonDifference(
                        clause_title=_title(c_a),
                        contract_a=_summary(c_a)[:220] or f"Present in '{name_a}'.",
                        contract_b=_summary(c_b)[:220] or f"Present in '{name_b}'.",
                        difference_type="Changed",
                        attention_level="high" if cat in ("Payment", "Termination", "Liability") else "medium",
                        category=cat,
                        ai_explanation=(
                            f"The wording of this provision differs between '{name_a}' and '{name_b}'. "
                            "Compare the quoted summaries and consider reviewing the change before signing."
                        ),
                    ))

        for key, c_b in index_b.items():
            if key not in matched_b:
                differences.append(ComparisonDifference(
                    clause_title=_title(c_b),
                    contract_a=f"No matching provision was identified in '{name_a}'.",
                    contract_b=f"Present in '{name_b}' ({_section(c_b)}, Page {_page(c_b)}): {_summary(c_b)[:220]}",
                    difference_type="Added",
                    attention_level="medium",
                    category=_category_for(_section(c_b), _title(c_b)),
                    ai_explanation=(
                        f"This is a new topic in '{name_b}' with no counterpart in '{name_a}'. "
                        "Consider reviewing what new duty, cost, or restriction it introduces."
                    ),
                ))

        # Payment-level deltas for the summary counters.
        payments_a = {_normalize(p.item): p.amount for p in (getattr(analysis_a, "payments", None) or [])} if analysis_a else {}
        payments_b = {_normalize(p.item): p.amount for p in (getattr(analysis_b, "payments", None) or [])} if analysis_b else {}
        payment_changes = sum(
            1 for item in set(payments_a) | set(payments_b)
            if payments_a.get(item) != payments_b.get(item)
        )

        obligations_a = {_normalize(ob.obligation) for ob in (getattr(analysis_a, "obligations", None) or [])} if analysis_a else set()
        obligations_b = {_normalize(ob.obligation) for ob in (getattr(analysis_b, "obligations", None) or [])} if analysis_b else set()
        new_obligations = len(obligations_b - obligations_a)

        changed = [d for d in differences if d.difference_type == "Changed"]
        summary = ComparisonSummary(
            total_changed=len([d for d in differences if d.difference_type in ("Added", "Removed", "Changed")]),
            new_obligations=new_obligations,
            payment_changes=payment_changes,
            wording_changes=len(changed),
        )

        return DocumentComparison(
            document_a_id=doc_a_id,
            document_b_id=doc_b_id,
            document_a_name=name_a,
            document_b_name=name_b,
            summary=summary,
            differences=differences[:_MAX_DIFFERENCES],
            disclaimer=DISCLAIMER,
        )

    @staticmethod
    def _sections_as_clauses(entry: dict) -> list:
        """Wraps raw extracted sections in a clause-like shape for comparison."""
        pseudo = []
        extracted = entry.get("extracted", {}) or {}
        for s in (extracted.get("sections") or [])[:15]:
            pseudo.append({
                "title": s.get("title", "Section"),
                "text": s.get("title", "Section"),
                "section": s.get("title", "General"),
                "page": s.get("start_page", 1),
            })
        return pseudo

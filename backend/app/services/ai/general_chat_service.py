import asyncio
import json
import re
import time
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from app.config import settings
from app.core.logging import logger
from app.services.ai.prompts import (
    SYSTEM_GENERAL_CHAT_PROMPT,
    GENERAL_CHAT_USER_PROMPT_TEMPLATE,
    SYSTEM_CROSS_DOC_CHAT_PROMPT,
    CROSS_DOC_CHAT_USER_PROMPT_TEMPLATE,
)


class CrossDocSource(BaseModel):
    document_id: str = Field(default="")
    document_name: str = Field(default="")
    page: int = Field(default=1)
    section: str = Field(default="General")
    snippet: str = Field(default="")


class GeneralChatResponse(BaseModel):
    conversation_id: str
    answer: str
    followup_questions: List[str] = Field(default_factory=list)
    sources: List[CrossDocSource] = Field(default_factory=list)
    confidence: str = Field(default="high")


class GeneralChatService:
    """
    LegalLens assistant with cross-document memory.
    Before answering, it searches the user's ENTIRE upload history for
    relevant excerpts; when found, the answer is grounded in those excerpts
    with per-document attribution. With no relevant uploads it behaves as a
    general legal-information assistant. Falls back to honest excerpt quotes
    when no API key is configured.
    """

    CROSS_DOC_TOP_K = 8

    @classmethod
    async def ask_question(cls, question: str, user_id: str, conversation_id: Optional[str] = None, *, save: bool = True, skip_retrieval: bool = False) -> GeneralChatResponse:
        if not conversation_id:
            conversation_id = f"conv-{uuid.uuid4().hex[:8]}"

        logger.info(f"General Chat: user='{user_id}' conv='{conversation_id}' q='{question[:80]}' skip_retrieval={skip_retrieval}")

        # Shared conversation store (document_id=None => library-wide chat).
        from app.services.ai.rag_service import RAGService
        history = RAGService.get_conversation_history(user_id, None, conversation_id)
        history_text = cls._format_history(history)

        # 1. Cross-document retrieval — skipped for pure Mode 1 general chat
        # to avoid unnecessary Qdrant calls and to keep answers general-knowledge.
        if not skip_retrieval:
            passages = cls._retrieve_user_passages(question, user_id)
            if passages:
                # For pure general questions like "What is an NDA?" don't force grounding;
                # only ground when passage is meaningfully relevant (overlap heuristic)
                if cls._should_ground(question, passages):
                    grounded = await cls._answer_from_user_documents(
                        question, passages, conversation_id, history_text)
                    if grounded:
                        if save:
                            cls._save_pair(user_id, conversation_id, question, grounded)
                        return grounded
                    fallback = cls._fallback_cross_doc_answer(question, passages, conversation_id)
                    if save:
                        cls._save_pair(user_id, conversation_id, question, fallback)
                    return fallback

        api_key = None
        from app.services.ai.gemini_keys import gemini_key_manager
        if gemini_key_manager.has_keys():
            for api_key in gemini_key_manager.iter_keys():
                try:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=api_key)
                    prompt = GENERAL_CHAT_USER_PROMPT_TEMPLATE.format(user_question=question)

                    config = types.GenerateContentConfig(
                        system_instruction=SYSTEM_GENERAL_CHAT_PROMPT,
                        response_mime_type="application/json",
                        temperature=0.3,
                    )

                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=settings.GEMINI_MODEL,
                        contents=prompt,
                        config=config
                    )

                    if response and response.text:
                        parsed = cls._parse_json(response.text, conversation_id)
                        if parsed:
                            gemini_key_manager.report_success(api_key)
                            logger.info(f"General Chat: Gemini answer generated for '{conversation_id}'.")
                            if save:
                                cls._save_pair(user_id, conversation_id, question, parsed)
                            return parsed
                    break  # non-quota path done; fall through to fallback
                except Exception as e:
                    if gemini_key_manager.is_quota_error(e):
                        gemini_key_manager.report_quota_failure(api_key)
                        continue  # quota exhausted -> fail over to next key
                    logger.error(f"Gemini general chat SDK error ({e}). Using fallback answer engine.")
                    break

        fallback = cls._generate_fallback_answer(question, conversation_id)
        if save:
            cls._save_pair(user_id, conversation_id, question, fallback)
        return fallback

    @staticmethod
    def _format_history(messages: List[dict]) -> str:
        if not messages:
            return "No previous conversation."
        lines = []
        for msg in messages[-10:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            lines.append(f"{role}: {msg.get('content')}")
        return "\n".join(lines)

    @classmethod
    def _save_pair(cls, user_id: str, conversation_id: str, question: str, resp: "GeneralChatResponse"):
        try:
            from app.services.ai.rag_service import RAGService
            RAGService._save_message_pair(
                user_id, None, conversation_id, question, resp.answer,
                [s.model_dump() for s in resp.sources],
                referenced=[s.document_id for s in resp.sources if s.document_id],
            )
        except Exception as e:
            logger.warning(f"General chat history save failed ({e}).")

    @classmethod
    def _retrieve_user_passages(cls, question: str, user_id: str) -> List[dict]:
        """Searches all vectors owned by the user (no document restriction)."""
        try:
            from app.services.ai.embedding_service import EmbeddingService
            from app.services.ai.vector_service import VectorDatabaseService
            from app.services.document_service import DocumentManager

            query_vector = EmbeddingService.generate_embedding(question)
            chunks = VectorDatabaseService.search_user_chunks(
                user_id, query_vector, top_k=cls.CROSS_DOC_TOP_K
            )
            # Resolve display names for chunks indexed before name tagging.
            for c in chunks:
                if not c.get("document_name") and c.get("document_id"):
                    entry = DocumentManager.get_document_by_id(c["document_id"], user_id)
                    if entry:
                        c["document_name"] = entry.get("metadata", {}).get("name", "")
            # Drop chunks with no usable text.
            return [c for c in chunks if (c.get("text") or "").strip()]
        except Exception as e:
            logger.warning(f"Cross-document retrieval failed ({e}). Using general guidance.")
            return []

    @classmethod
    def _context_text(cls, passages: List[dict]) -> str:
        blocks = []
        for c in passages:
            doc_name = c.get("document_name") or c.get("document_id") or "Uploaded document"
            blocks.append(
                f"--- Document '{doc_name}' • Page {c.get('page_number', 1)} • "
                f"Section '{c.get('section', 'General')}' ---\n{(c.get('text') or '')[:900]}"
            )
        return "\n\n".join(blocks)

    @classmethod
    def _passage_sources(cls, passages: List[dict], limit: int = 4) -> List[CrossDocSource]:
        sources: List[CrossDocSource] = []
        seen = set()
        for c in passages:
            key = (c.get("document_id"), c.get("page_number"))
            if key in seen:
                continue
            seen.add(key)
            sources.append(CrossDocSource(
                document_id=c.get("document_id") or "",
                document_name=c.get("document_name") or "",
                page=c.get("page_number", 1),
                section=c.get("section", "General"),
                snippet=(c.get("text") or "")[:160],
            ))
            if len(sources) >= limit:
                break
        return sources

    @classmethod
    async def _answer_from_user_documents(
        cls, question: str, passages: List[dict], conversation_id: str,
        history_text: str = "No previous conversation."
    ) -> Optional[GeneralChatResponse]:
        from app.services.ai.gemini_keys import gemini_key_manager
        if not gemini_key_manager.has_keys():
            return None
        for api_key in gemini_key_manager.iter_keys():
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)
                prompt = CROSS_DOC_CHAT_USER_PROMPT_TEMPLATE.format(
                    user_question=question,
                    chat_history_text=history_text,
                    context_text=cls._context_text(passages),
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
                    data = json.loads(response.text)
                    raw_sources = data.get("sources") or []
                    sources = []
                    for s in raw_sources:
                        if isinstance(s, dict):
                            sources.append(CrossDocSource(
                                document_id=str(s.get("document_id", "")),
                                document_name=str(s.get("document_name", "")),
                                page=int(s.get("page", 1)) if str(s.get("page", 1)).isdigit() else 1,
                                section=str(s.get("section", "General")),
                                snippet=str(s.get("snippet", "")),
                            ))
                    if not sources:
                        sources = cls._passage_sources(passages)
                    gemini_key_manager.report_success(api_key)
                    return GeneralChatResponse(
                        conversation_id=conversation_id,
                        answer=data.get("answer", ""),
                        followup_questions=data.get("followup_questions", []),
                        sources=sources,
                        confidence=data.get("confidence", "high"),
                    )
                return None
            except Exception as e:
                if gemini_key_manager.is_quota_error(e):
                    gemini_key_manager.report_quota_failure(api_key)
                    continue  # quota exhausted -> fail over to next key
                logger.error(f"Gemini cross-document chat error ({e}). Using excerpt fallback.")
                return None
        return None

    @classmethod
    def _fallback_cross_doc_answer(
        cls, question: str, passages: List[dict], conversation_id: str
    ) -> GeneralChatResponse:
        """Honest offline answer: direct quotes from the user's own documents."""
        top = passages[0]
        doc_name = top.get("document_name") or "your uploaded document"
        quote = (top.get("text") or "").strip()[:600]
        answer = (
            f"Here is the most relevant text from your uploads "
            f"('{doc_name}', Page {top.get('page_number', 1)}, Section '{top.get('section', 'General')}'):\n\n"
            f"> {quote}\n\n"
            "The above is a direct excerpt from your document. "
            "Connect the live Gemini AI service for a plain-language interpretation across all your uploads.\n\n"
            "*LegalLens provides informational assistance and does not replace professional legal advice.*"
        )
        return GeneralChatResponse(
            conversation_id=conversation_id,
            answer=answer,
            followup_questions=[
                "What else do my documents say about this topic?",
                "Which of my documents has the strictest terms here?",
            ],
            sources=cls._passage_sources(passages),
            confidence="medium",
        )

    @classmethod
    def _parse_json(cls, text: str, conversation_id: str) -> Optional[GeneralChatResponse]:
        try:
            data = json.loads(text)
            return GeneralChatResponse(
                conversation_id=conversation_id,
                answer=data.get("answer", ""),
                followup_questions=data.get("followup_questions", [])
            )
        except Exception as e:
            logger.warning(f"General chat JSON parse error ({e}). Using regex recovery...")
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    return GeneralChatResponse(
                        conversation_id=conversation_id,
                        answer=data.get("answer", ""),
                        followup_questions=data.get("followup_questions", [])
                    )
                except Exception:
                    pass
        return None

    # Topic -> plain-language educational answer + follow-ups. Used by the
    # offline fallback so the assistant stays maximally useful even when the
    # live Gemini service is unreachable or quota is exhausted.
    LEGAL_TOPICS = {
        "non-compete": (
            "Non-compete clauses restrict you from working for or starting competing businesses for a set period "
            "after leaving a company. Enforceability varies widely by state and by factors like duration, "
            "geographic scope, and the legitimate business interest protected. Many jurisdictions limit or ban "
            "them for low-wage roles, and some states require reasonable terms to be enforceable at all.\n\n"
            "To know how this applies to your specific contract, upload the agreement and I can point to the exact "
            "clause.",
            ["How long can a non-compete reasonably last?", "What makes a non-compete unenforceable?"],
        ),
        "confidentiality": (
            "Confidentiality (NDA) clauses bind a party to keep certain information secret. They typically cover "
            "what counts as confidential, permitted disclosures (e.g. to advisors), how long the duty lasts, and "
            "remedies for breach. Before signing, check the definition of confidential information and whether "
            "standard industry practices or public knowledge are carved out.\n\n"
            "Upload your agreement and I can flag the exact confidentiality terms in it.",
            ["What should a fair NDA contain?", "How long should confidentiality last?"],
        ),
        "indemnif": (
            "An indemnification clause makes one party responsible for losses (including legal costs) the other "
            "party suffers in defined situations. Pay attention to the trigger events, whether it covers third-party "
            "claims, liability caps, and any carve-outs. Indemnities often overlap with insurance — check your "
            "coverage before agreeing to broad indemnities.\n\n"
            "Upload your document and I'll break down the specific indemnity terms it sets out.",
            ["What is a broad indemnity vs a narrow one?", "Should I ask for a liability cap?"],
        ),
        "notice period": (
            "A notice period is the advance warning either party must give before ending an agreement. Contracts "
            "typically require written notice (for example 30–90 days) and may spell out penalties for early exit, "
            "such as repayment of bonuses, relocation costs, or other benefits. Cure periods — a short window to fix "
            "a breach before termination — are also common.\n\n"
            "Upload your contract and I can break down its exact termination and notice terms.",
            ["What is a cure period?", "Can I negotiate a shorter notice period?"],
        ),
        "salary": (
            "Salary and bonus terms vary by contract. Common pieces include base pay, pay frequency, performance-based "
            "bonuses, and clawback provisions that let an employer recover paid bonuses under certain conditions.\n\n"
            "Upload the document and ask me about its payment sections for a precise breakdown.",
            ["What is a clawback clause?", "What should I check in a salary offer?"],
        ),
        "bonus": (
            "Salary and bonus terms vary by contract. Common pieces include base pay, pay frequency, performance-based "
            "bonuses, and clawback provisions that let an employer recover paid bonuses under certain conditions.\n\n"
            "Upload the document and ask me about its payment sections for a precise breakdown.",
            ["What is a clawback clause?", "What should I check in a salary offer?"],
        ),
        "clawback": (
            "A clawback provision lets an employer recover paid bonuses or equity if performance was later found "
            "overstated, or if the employee commits misconduct. Check the trigger conditions, the clawback window, "
            "and the amount that can be recovered — they vary widely between agreements.\n\n"
            "Upload your offer/contract and I'll find its specific clawback terms.",
            ["What triggers a clawback?", "How can I negotiate a better clawback clause?"],
        ),
        "auto-renew": (
            "Automatic renewal means a contract extends itself for another term unless you give written notice before "
            "the deadline. A common trap is missing that deadline and being locked in for another year. Always check "
            "the renewal term length and the advance notice required to opt out.\n\n"
            "Upload the agreement and I can flag the exact renewal and opt-out deadlines for you.",
            ["What happens if I miss the renewal opt-out deadline?", "Can I negotiate auto-renewal away?"],
        ),
        "renew": (
            "Automatic renewal means a contract extends itself for another term unless you give written notice before "
            "the deadline. A common trap is missing that deadline and being locked in for another year. Always check "
            "the renewal term length and the advance notice required to opt out.\n\n"
            "Upload the agreement and I can flag the exact renewal and opt-out deadlines for you.",
            ["What happens if I miss the renewal opt-out deadline?", "Can I negotiate auto-renewal away?"],
        ),
        "late fee": (
            "Late payment fees are penalties charged when an invoice is not paid by its due date. They are usually a "
            "flat amount or a percentage (for example 1–1.5% per month). Note that some amounts may be limited by "
            "consumer protection laws (e.g. penalties cannot be excessive).\n\n"
            "Upload the invoice or contract and I can point out its exact late-fee terms.",
            ["What is a reasonable late fee?", "When are late fees unenforceable?"],
        ),
        "interest": (
            "Interest clauses set the rate charged on late or outstanding balances. Rates can be simple or compound, "
            "and some are limited by law (usury limits) depending on the jurisdiction and type of lender.\n\n"
            "Upload the document to see the specific interest terms it contains.",
            ["What is the difference between simple and compound interest?", "What is a usury limit?"],
        ),
        "force majeure": (
            "A force majeure clause excuses a party from performing when an extraordinary event occurs — natural "
            "disasters, war, pandemics, strikes. Scope, notice obligations, and what counts as an 'act of God' vary "
            "greatly, so read which events are listed and what each party must do.\n\n"
            "Upload your contract and I'll examine its force majeure provision.",
            ["Does force majeure cover pandemics?", "What should I check in a force majeure clause?"],
        ),
        "liability cap": (
            "A liability cap limits the maximum damages one party can be required to pay (e.g. to fees paid under the "
            "agreement). Caps are common in software and service contracts. Also watch for carve-outs for "
            "confidentiality breaches, indemnities, and gross negligence, which often sit outside the cap.\n\n"
            "Upload your contract and I'll locate its liability cap and carve-outs.",
            ["What is a reasonable liability cap?", "What are common carve-outs?"],
        ),
        "warrant": (
            "Warranties are formal promises about the state of goods, services, or information. 'As is' language "
            "disclaims most warranties, while express warranties promise specific features. Check what is warranted, "
            "for how long, and what your remedies are if a warranty is breached.\n\n"
            "Upload the contract so I can identify its warranty and disclaimer language.",
            ["What is the difference between express and implied warranties?", "What happens if a warranty is breached?"],
        ),
        "jurisdiction": (
            "A governing law / jurisdiction clause states which country or state's law applies and which courts will "
            "resolve disputes. This can greatly affect your rights, so check it carefully — especially in cross-border "
            "agreements. Also look for dispute resolution (arbitration vs courts) choices.\n\n"
            "Upload your contract and I'll tell you exactly what its governing-law clause says.",
            ["What is arbitration vs litigation?", "Why does governing law matter?"],
        ),
        "arbitration": (
            "Arbitration is a private dispute-resolution process instead of court litigation; the arbitrator's decision "
            "is usually binding. Arbitration can be faster and cheaper, but you generally give up the right to a jury "
            "trial and class actions. Check who pays the fees and where the hearing takes place.\n\n"
            "Upload the contract to review its arbitration clause.",
            ["Is arbitration better than court?", "Can I opt out of arbitration?"],
        ),
        "renewal": (
            "Automatic renewal means a contract extends itself for another term unless you give written notice before "
            "the deadline. A common trap is missing that deadline and being locked in for another year. Always check "
            "the renewal term length and the advance notice required to opt out.\n\n"
            "Upload the agreement and I can flag the exact renewal and opt-out deadlines for you.",
            ["What happens if I miss the renewal opt-out deadline?", "Can I negotiate auto-renewal away?"],
        ),
        "severance": (
            "Severance pay is compensation provided when employment ends, often in exchange for a release of claims. "
            "Check how the amount is calculated (weeks of pay per year of service), the treatment of bonus/equity, "
            "continued benefits (COBRA), and the release's scope before signing.\n\n"
            "Upload your severance agreement and I'll highlight what it actually offers.",
            ["What should a fair severance package include?", "Should I sign a release of claims?"],
        ),
        "equity": (
            "Equity in an offer usually means stock options or restricted stock units (RSUs). Key terms are the vesting "
            "schedule, exercise price, cliff period, what happens on termination, and any acceleration provisions. "
            "Option and equity grants can have material tax consequences.\n\n"
            "Upload your offer letter and I'll find its equity/vesting terms.",
            ["What is a vesting cliff?", "What happens to my options if I leave?"],
        ),
        "vesting": (
            "Vesting determines when you actually own your shares or options — usually over a schedule (e.g. 4 years, "
            "with a 1-year cliff). After a cliff, grants typically vest monthly. Leaving before cliff usually forfeits "
            "everything; leaving after may allow exercising vested options only.\n\n"
            "Upload your agreement to see its exact vesting schedule.",
            ["What happens if I leave before my cliff?", "What is an exercise window after termination?"],
        ),
        "non-solicit": (
            "Non-solicitation clauses restrict you from recruiting your employer's employees or taking their clients "
            "after you leave. Scope (which clients, for how long, in what region) matters a lot for enforceability.\n\n"
            "Upload your agreement and I can examine its non-solicitation restrictions.",
            ["What is the difference between non-compete and non-solicit?", "Are these clauses enforceable?"],
        ),
        "garden leave": (
            "Garden leave means you remain employed and paid but do not work during the notice period — it is often "
            "used to keep a departing employee away from clients. It can bypass stricter non-competes.\n\n"
            "If your contract mentions garden leave, upload it and I'll summarize the terms.",
            ["Why do employers use garden leave?", "Am I paid during garden leave?"],
        ),
        "intellectual property": (
            "Intellectual property clauses assign ownership of work product. In employment, this is often an "
            "'assignment of inventions' clause granting the employer rights to your creations. Check what is covered, "
            "whether pre-existing IP is carved out, and how disputes are handled.\n\n"
            "Upload your contract and I'll analyze its IP provisions.",
            ["Do employers really own everything I create?", "What is a 'pre-existing IP' carve-out?"],
        ),
        "assignment": (
            "An assignment clause controls whether a party can transfer the contract to someone else (e.g. another "
            "company). If assignment is restricted, an acquisition or restructuring may need consent. This is common "
            "and often negotiated.\n\n"
            "Upload the contract and I'll show you what its assignment clause says.",
            ["What happens if my company is acquired?", "When can a contract be assigned without consent?"],
        ),
        "covenant": (
            "Restrictive covenants (non-compete, non-solicit, confidentiality) limit what you can do after leaving. "
            "Their enforceability varies by jurisdiction and by how reasonable the scope is. Some jurisdictions have "
            "banned non-competes for most employees.\n\n"
            "Upload your agreement and I'll look at its restrictive covenant clauses.",
            ["Are restrictive covenants enforceable?", "How do I know if a covenant is too broad?"],
        ),
        "notice": (
            "Notice provisions govern how (and by when) parties must notify each other — e.g. written notice, email "
            "to a specific address, or 30 days before renewing. Missing a notice deadline can mean losing rights, so "
            "check both the method and the deadline.\n\n"
            "Upload your contract to review its notice clause.",
            ["What happens if I miss a notice deadline?", "Is email notice valid?"],
        ),
        "sign": (
            "Before signing, focus on: any auto-renewal or notice deadlines, payment and late-fee terms, liability caps "
            "and carve-outs, restrictive covenants, termination rights, and dispute resolution. If a fee or deadline "
            "isn't clear, ask for written clarification — silence in a contract rarely protects you.\n\n"
            "Upload the document and I can run a full risk analysis on it.",
            ["What are the biggest risks in this document?", "What should I ask a lawyer before signing?"],
        ),
        "negotiat": (
            "Common negotiation levers include: removing auto-renewal or shortening its term, adding a liability cap, "
            "narrowing restrictive covenants, extending payment terms, adding exit/cure periods, and specifying "
            "renewal notice. Most providers expect reasonable edits — ask in writing before signing.\n\n"
            "Upload the contract and I can flag which terms are typically negotiable.",
            ["What is usually negotiable in a contract?", "How do I ask for better terms professionally?"],
        ),
        "rent": (
            "When renting, key terms include the monthly rent and escalation, security deposit and return timeline, "
            "maintenance responsibilities, subletting rights, notice periods, and termination/early-exit costs. Some "
            "lease terms (like excessive late fees) may be limited by law.\n\n"
            "Upload your lease and I can highlight the terms that matter most.",
            ["What should I check before signing a lease?", "When can a landlord withhold my deposit?"],
        ),
        "deposit": (
            "Security deposits are funds held against damage or unpaid rent. Most states limit how much can be charged "
            "and require the return (with an itemized deduction list) within a set time after move-out. Keep move-in "
            "photos and a signed condition checklist.\n\n"
            "Upload your lease to review its deposit terms.",
            ["How long can a landlord keep my deposit?", "Can a landlord charge a non-refundable deposit?"],
        ),
        "lease": (
            "When renting, key terms include the monthly rent and escalation, security deposit and return timeline, "
            "maintenance responsibilities, subletting rights, notice periods, and termination/early-exit costs. Some "
            "lease terms (like excessive late fees) may be limited by law.\n\n"
            "Upload your lease and I can highlight the terms that matter most.",
            ["What should I check before signing a lease?", "When can a landlord withhold my deposit?"],
        ),
        "eviction": (
            "Eviction laws vary by state but generally a landlord needs proper notice and, for nonpayment, a formal "
            "process before removing a tenant. Tenants often have defenses (failure to maintain the unit, illegal "
            "retaliation, payment tendered). Consult your local housing agency or a lawyer for your specific case.\n\n"
            "If you have a lease or notice, upload it and I can help review it.",
            ["What are my rights if the landlord files for eviction?", "How do I dispute an eviction notice?"],
        ),
        "tenant": (
            "Tenant rights and landlord duties vary by state, but landlords generally must maintain the unit in a safe, "
            "habitable condition, provide required notice before entry, and follow legal process for eviction. Tenant "
            "responsibilities typically include timely rent and not damaging the property.\n\n"
            "Upload your lease or any notice you received for a detailed review.",
            ["What can my landlord legally do?", "How do I get out of a lease early?"],
        ),
        "landlord": (
            "Landlords generally must maintain the unit in a safe, habitable condition, provide proper notice before "
            "entry, and follow legal process for eviction. Tenant rights vary by state — leases cannot waive many "
            "statutory tenant protections.\n\n"
            "Upload your lease or a landlord notice and I'll review it.",
            ["What are a landlord's main obligations?", "How do I handle a landlord dispute?"],
        ),
        "warranty law": (
            "Warranty law protects buyers when goods don't perform as promised. Express warranties are explicit "
            "promises; implied warranties (merchantability, fitness for purpose) arise automatically in most states "
            "unless disclaimed. Remedies often include repair, replacement, or refund.\n\n"
            "If you have a warranty document, upload it for analysis.",
            ["What is an implied warranty?", "How do I claim under warranty?"],
        ),
        "refund": (
            "Refund policies and statutory return rights differ by product and jurisdiction. Check the refund window, "
            "conditions (unopened vs damaged), restocking fees, and how refunds are paid before you buy.\n\n"
            "Upload your receipt or policy document and I'll look at its refund terms.",
            ["What are my consumer return rights?", "Can a store refuse a refund?"],
        ),
        "consumer": (
            "Consumer protection laws typically grant rights to refunds, honest advertising, and safe products, and "
            "may limit unfair contract terms such as hidden fees or excessive penalties. The specific protections vary "
            "by jurisdiction and by type of purchase.\n\n"
            "Upload the receipt, policy, or terms and I'll review them.",
            ["What are my rights if a product is defective?", "Can a business change terms after purchase?"],
        ),
        "invoice": (
            "When reviewing an invoice, check the amount, due date, late-fee and interest terms, and whether the "
            "services/goods match the agreement. Pay deadlines are usually strict — missing one can trigger penalties "
            "or suspension.\n\n"
            "Upload the invoice or agreement and I'll point out the key terms.",
            ["What happens if I pay late?", "Can I dispute an invoice?"],
        ),
        "payment": (
            "Payment terms define amounts, due dates, and consequences (late fees, interest, suspension) for non-payment. "
            "Check due dates, invoicing triggers, and whether payment requires acceptance of work before it's due.\n\n"
            "Upload the contract or invoice and I'll analyze the payment clauses.",
            ["When can I withhold payment?", "What are common payment deadlines?"],
        ),
        "liability": (
            "Liability clauses allocate who bears losses and risks. Common features are liability caps, disclaimers "
            "for indirect/consequential damages, and carve-outs. These are among the most commercially important terms "
            "in any contract.\n\n"
            "Upload your contract and I'll analyze how liability is allocated in it.",
            ["What are consequential damages?", "What is a mutual liability cap?"],
        ),
        "damage": (
            "Damages clauses describe what one party pays if the other suffers loss. Types include direct, consequential, "
            "and liquidated damages. Many contracts exclude consequential damages and set a cap on all liability.\n\n"
            "Upload your document and I'll explain the damages provisions it contains.",
            ["What is the difference between direct and consequential damages?", "What are liquidated damages?"],
        ),
        "liquidated": (
            "Liquidated damages are a pre-agreed amount payable for a specific breach (e.g. a fixed daily penalty for "
            "delays). Courts may reject them if the amount is an unconscionable penalty rather than a genuine estimate "
            "of loss.\n\n"
            "Upload the contract and I'll review its liquidated damages clause.",
            ["Are liquidated damages different from penalties?", "When are they enforceable?"],
        ),
        "privacy": (
            "Privacy policies and data-protection clauses describe what personal data is collected, why, how long it's "
            "kept, and who it is shared with. Laws like GDPR make consent, access, and deletion rights important.\n\n"
            "Upload the policy or agreement and I'll summarize its data-privacy terms.",
            ["What should a good privacy policy include?", "What are my rights under GDPR?"],
        ),
        "data": (
            "Data-protection clauses address how personal data is handled, secured, and shared. Look for the lawful "
            "basis, retention periods, security measures, and whether subcontractors are bound as well.\n\n"
            "Upload your agreement and I'll review its data-handling terms.",
            ["What is a Data Processing Agreement (DPA)?", "What should a DPA include?"],
        ),
        "employment": (
            "Employment terms vary by contract type and jurisdiction. Key areas include compensation, benefits, "
            "termination notice, restrictive covenants, IP assignment, and dispute resolution. Some change-of-"
            "employment rights (minimum wage, leave) cannot be contracted away.\n\n"
            "Upload your offer or employment agreement and I'll analyze it.",
            ["What should I check in an employment contract?", "What are my rights as an employee?"],
        ),
        "offer": (
            "Offer letters and employment contracts set out compensation, role, start date, at-will or fixed term, "
            "and often restrictive covenants. Check the compensation breakdown, termination notice, and any vesting "
            "or bonus terms before signing.\n\n"
            "Upload your offer letter and I'll review the key terms.",
            ["Is an offer letter legally binding?", "What should I negotiate in an offer?"],
        ),
        "gross negligence": (
            "Gross negligence is conduct far below the standard of care — beyond mere carelessness. Many contracts cap "
            "liability but carve out gross negligence; this carve-out is important because otherwise the cap could "
            "reach the negligent party's big losses.\n\n"
            "Upload your contract and I'll check how gross negligence is treated.",
            ["What counts as gross negligence?", "Why is it carved out of liability caps?"],
        ),
        "fraud": (
            "Fraudulent conduct is misrepresentation intended to deceive. Contracts often exclude fraud from liability "
            "caps and disclaimers, since parties cannot generally contract away liability for their own fraud.\n\n"
            "If a fraud concern arises from a document, upload it and I'll help examine the relevant clauses.",
            ["What is fraud in contract law?", "Can fraud be excluded from a contract?"],
        ),
        "breach": (
            "A breach occurs when a party fails to perform an obligation. Consequences depend on the contract — cure "
            "periods, penalties, termination rights, and damages. Material vs minor breach changes whether the other "
            "party can walk away.\n\n"
            "Upload the contract and I'll explain what happens on a breach.",
            ["What is the difference between a material and minor breach?", "What can I do if the other side breaches?"],
        ),
        "cure": (
            "A cure period is a window (e.g. 10–30 days) to fix a breach before the other party can terminate or claim "
            "damages. Check both how long it lasts and who must give notice of the breach to start the clock.\n\n"
            "Upload your contract and I'll find its cure-period terms.",
            ["When does the cure period start?", "What happens if I can't cure the breach in time?"],
        ),
        "dispute": (
            "Dispute-resolution clauses decide how disagreements are handled: negotiation, mediation, arbitration, or "
            "court. Also watch governing law, venue, and any requirement to use a specific forum within a time limit.\n\n"
            "Upload your contract and I'll summarize its dispute-resolution terms.",
            ["What is mediation vs arbitration?", "Can I sue in small claims court instead?"],
        ),
        "subletting": (
            "Subletting lets a tenant lease the unit to someone else. Many leases require the landlord's consent, and "
            "some states guarantee tenant rights to sublet with reasonable conditions. Check consent requirements and "
            "any added fees.\n\n"
            "Upload your lease to see its subletting terms.",
            ["Can my landlord refuse a sublease?", "What is the difference between sublet and assign?"],
        ),
        "milestone": (
            "Milestone clauses tie payments or deliveries to defined progress points. Check what evidence is needed to "
            "trigger each milestone, the timing, and what happens if a milestone is missed.\n\n"
            "Upload your contract and I'll review the milestone schedule.",
            ["What if a milestone is delayed?", "How are milestone payments structured?"],
        ),
        "scope": (
            "Scope-of-work clauses define exactly what must be delivered. Vague scope often leads to disputes about "
            "extra work. Check deliverables, exclusions, assumptions, and change-order processes.\n\n"
            "Upload the agreement and I'll examine the scope definition.",
            ["What should a clear scope of work include?", "How do I handle scope creep?"],
        ),
        "change order": (
            "Change-order provisions set out how scope or pricing changes are approved mid-contract — usually in writing "
            "signed by both sides. Without one, verbal changes can create disputes about price and deadline.\n\n"
            "Upload your contract and I'll locate its change-process terms.",
            ["What is a change order?", "Can verbal changes bind me?"],
        ),
        "termination fee": (
            "Early-termination fees (or cancellation fees) charge a party for ending an agreement before its term. "
            "Check the fee formula, notice windows, and exceptions (e.g. convenience vs breach).\n\n"
            "Upload your contract and I'll find the early-exit cost terms.",
            ["Is an early-termination fee enforceable?", "How can I reduce termination fees?"],
        ),
        "agreement": (
            "An agreement is a mutual understanding that creates enforceable obligations — often combining an offer and "
            "acceptance for something of value. Key ingredients are offer, acceptance, and consideration (value "
            "exchanged). Verbal agreements can bind, but written ones are far easier to prove and enforce.\n\n"
            "Upload your agreement and I'll analyze what it commits you to.",
            ["What makes a contract legally binding?", "Is a verbal agreement enforceable?"],
        ),
        "contract law": (
            "Contract law governs enforceable promises. The essential elements are offer, acceptance, consideration, "
            "capacity, and a lawful purpose. If an essential term is missing or a clause is unconscionable, a court may "
            "limit or void part of the agreement — but that is case-specific.\n\n"
            "Upload a contract and I can explain exactly how these principles apply to it.",
            ["What are the elements of a valid contract?", "When is a contract void or voidable?"],
        ),
        "company": (
            "When evaluating company terms apply: watch governing law, auto-renewal, liability caps, arbitration, and "
            "data handling. Company agreements often include broad indemnities and one-sided termination — read them "
            "carefully.\n\n"
            "Upload the agreement and I'll run through its important commercial terms.",
            ["What should I check in a service agreement?", "How do I manage vendor contracts?"],
        ),
        "service": (
            "Service agreements define deliverables, timelines, fees, payment schedules, warranties, and liability. Key "
            "watch-points are the scope of work, change-order process, termination rights, and any liability caps or "
            "exclusions.\n\n"
            "Upload your service agreement and I'll analyze its core terms.",
            ["What should a service agreement include?", "What is a Statement of Work (SOW)?"],
        ),
        "vendor": (
            "Vendor/software agreements commonly contain auto-renewal, liability caps, data-processing terms, and "
            "service-level commitments. Check renewal notice windows, pricing escalations, and exit/transition help "
            "before signing.\n\n"
            "Upload your vendor agreement and I'll highlight what to watch.",
            ["What is an SLA and why does it matter?", "How do I negotiate SaaS contracts?"],
        ),
        "software": (
            "Software/SaaS agreements include subscription fees, renewal terms, service levels, data security, and "
            "liability caps. Common concerns are auto-renewal, one-sided termination, and limits on uptime remedies.\n\n"
            "Upload the software agreement and I'll analyze its key terms.",
            ["What is an SLA in a SaaS contract?", "Can I negotiate the liability cap?"],
        ),
        "nonpayment": (
            "Nonpayment provisions describe what happens if a party fails to pay — late fees, interest, suspension of "
            "services, or termination. Check grace periods and notice requirements before penalties kick in.\n\n"
            "Upload your contract and I'll outline its nonpayment consequences.",
            ["When can services be suspended for nonpayment?", "What late fees are reasonable?"],
        ),
        "subscription": (
            "Subscription agreements bundle a recurring fee with ongoing access. Watch renewal timing, cancellation "
            "notice, price increases, and auto-renewal opt-outs.\n\n"
            "Upload your subscription agreement and I'll flag the deadlines that matter.",
            ["How do I cancel a subscription safely?", "Can price increases be contested?"],
        ),
        "amend": (
            "Amendment clauses define how a contract can be changed later — usually a written document signed by both "
            "parties. Important: some deals include a 'no oral modification' clause, so informal emails may not bind.\n\n"
            "Upload the contract and I'll explain how its amendment clause works.",
            ["Can a contract be changed verbally?", "How do I formally amend a contract?"],
        ),
        "entire agreement": (
            "An 'entire agreement' clause states the written contract is the full agreement, overriding earlier "
            "discussions. This means promised-but-unwritten terms may not be enforceable.\n\n"
            "Upload your contract and I'll point out its entire-agreement clause.",
            ["Does the entire-agreement clause matter?", "What if something important was only promised verbally?"],
        ),
        "counterpart": (
            "A counterpart clause lets the parties sign separate copies of the same agreement, each treated as one "
            "original. It is a routine administrative provision and rarely needs heavy negotiation.\n\n"
            "Happy to review the rest of your contract — upload it and I'll focus on the substantive terms.",
            ["What is a counterparts clause?", "Does e-signature satisfy a counterparts clause?"],
        ),
        "severab": (
            "A severability clause says that if one part of the contract is found invalid, the rest still stands. It "
            "protects the agreement's core from being destroyed by one unenforceable clause.\n\n"
            "Upload your contract and I'll check its severability provision.",
            ["What does severability mean in practice?", "What happens without a severability clause?"],
        ),
        "survival": (
            "A survival clause says certain sections (confidentiality, indemnity, IP) remain in force after the "
            "contract ends. Check how long the obligations survive termination.\n\n"
            "Upload your agreement and I'll summarize its survival terms.",
            ["Which clauses usually survive termination?", "How long should survival be?"],
        ),
        "insurance": (
            "Insurance clauses require a party to maintain certain coverage (e.g. general liability, errors & "
            "omissions) and name the other party as an additional insured. Confirm the required limits and that your "
            "insurer can endorse the naming requirement.\n\n"
            "Upload the agreement and I'll list the insurance requirements it imposes.",
            ["What insurance limits are standard?", "What does 'additional insured' mean?"],
        ),
        "notice of default": (
            "A notice-of-default clause requires the non-breaching party to give written notice and time to remedy "
            "before exercising remedies. Check the notice channel, the cure window, and what happens if no cure "
            "occurs.\n\n"
            "Upload your contract and I'll find its default-notice terms.",
            ["What is a default notice?", "How long is a typical cure period?"],
        ),
        "default": (
            "Default occurs when a party fails to perform a required obligation. Contracts typically set out what "
            "counts as default, required notices, cure periods, and the remedies (penalties, termination, damages) "
            "that follow.\n\n"
            "Upload your contract and I'll explain its default provisions.",
            ["What counts as a default?", "What remedies follow a default?"],
        ),
        "transition": (
            "Transition or exit clauses govern what happens when the agreement ends — data export, handover, "
            "transition assistance. Watch for transition fees and how much help you get after termination.\n\n"
            "Upload your agreement and I'll examine its exit/transition terms.",
            ["What is transition assistance?", "How long does the transition period last?"],
        ),
        "audit": (
            "Audit clauses let one party (often a licensor) inspect the other's records to verify compliance, such as "
            "license usage. Check the notice required, who pays for the audit, and how overages are handled.\n\n"
            "Upload your contract and I'll review its audit terms.",
            ["What should an audit clause include?", "Who pays for an audit?"],
        ),
        "third party": (
            "Third-party terms (e.g. 'third-party beneficiary', 'third-party software') create rights/obligations for "
            "people or companies not signing the contract. If a contract grants third parties rights, its terms can be "
            "enforced by those parties too.\n\n"
            "Upload your agreement and I'll explain who gains rights under it.",
            ["What is a third-party beneficiary?", "Can a non-party enforce a contract?"],
        ),
        }

    @classmethod
    def _match_topic(cls, q_lower: str):
        """Return (key, text, followups) for the best-matching legal topic."""
        best_key = None
        for kw in cls.LEGAL_TOPICS:
            if kw in q_lower and (best_key is None or len(kw) > len(best_key)):
                best_key = kw
        if not best_key or best_key.endswith(" "):
            return None
        entry = cls.LEGAL_TOPICS.get(best_key)
        if not entry:
            return None
        return best_key, entry[0], entry[1]

    @classmethod
    def _generate_fallback_answer(cls, question: str, conversation_id: str) -> GeneralChatResponse:
        q_lower = question.lower().strip()

        if not q_lower or q_lower in (
            "hi", "hii", "hiii", "hey", "hello", "hai", "hola", "yo", "sup",
            "ok", "okay", "cool", "great", "nice",
        ) or any(p in q_lower for p in (
            "good morning", "good afternoon", "good evening", "how are you",
        )):
            return GeneralChatResponse(
                conversation_id=conversation_id,
                answer=(
                    "Hello! I'm LegalLens AI — your legal document assistant. I can explain "
                    "contracts in plain language, flag risks and deadlines, compare documents, "
                    "and answer general legal questions.\n\n"
                    "Upload a document to get started, or just ask me anything — "
                    "for example, \"What is a non-compete clause?\".\n\n"
                    "*LegalLens provides informational assistance and does not replace professional legal advice.*"
                ),
                followup_questions=[
                    "What should I check before signing a contract?",
                    "What is a non-compete clause?",
                    "How do I upload and analyse a document?",
                ],
            )

        if any(p in q_lower for p in ("thank", "thanks")):
            return GeneralChatResponse(
                conversation_id=conversation_id,
                answer=(
                    "You're welcome! Ask me anything else — about your documents "
                    "or any general legal topic.\n\n"
                    "*LegalLens provides informational assistance and does not replace professional legal advice.*"
                ),
                followup_questions=[
                    "What should I check before signing a contract?",
                    "What are common risky clauses?",
                ],
            )

        matched = cls._match_topic(q_lower)
        if matched:
            _key, answer, followups = matched
            return GeneralChatResponse(
                conversation_id=conversation_id,
                answer=(
                    f"{answer}\n\n"
                    "*LegalLens provides informational assistance and does not replace professional legal advice.*"
                ),
                followup_questions=followups,
            )

        answer = (
            f"Here is some general guidance on your question about \"{question}\":\n\n"
            "Most everyday legal questions depend on the specific contract, the governing law, and the facts of your "
            "situation. As a general rule, always read the fine print for notice deadlines, payment terms, liability "
            "limits, and termination rights before signing.\n\n"
            "If you have a specific document in mind, upload it here and I can read the actual clauses and give you "
            "a grounded, clause-by-clause breakdown.\n\n"
            "*LegalLens provides informational assistance and does not replace professional legal advice.*"
        )
        followups = [
            "What should I check before signing a contract?",
            "What are common risky clauses?",
            "How do I negotiate better contract terms?"
        ]

        # Set the followup suggestions off the matched topic (when present).
        return GeneralChatResponse(
            conversation_id=conversation_id,
            answer=answer,
            followup_questions=followups
        )

    @classmethod
    def _should_ground(cls, question: str, passages: List[dict]) -> bool:
        """Only ground in docs when the question meaningfully overlaps retrieved text."""
        q = question.lower()
        # Explicit document reference → always ground
        if any(kw in q for kw in ["my document", "my contract", "this document", "this contract", "uploaded", "my file"]):
            return True
        # If top passage shares significant lexical overlap with question, ground
        if passages and passages[0].get("text"):
            top_text = passages[0].get("text", "").lower()
            q_words = [w for w in q.split() if len(w) > 3]
            if q_words:
                overlap = sum(1 for w in q_words if w in top_text)
                if overlap / max(1, len(q_words)) >= 0.3:
                    return True
        return False

    @classmethod
    async def ask_pure_general(cls, question: str, user_id: str, conversation_id: Optional[str] = None, *, save: bool = True) -> GeneralChatResponse:
        """Pure Mode 1: no Qdrant retrieval, just Gemini + fallback FAQ."""
        return await cls.ask_question(question, user_id, conversation_id, save=save, skip_retrieval=True)
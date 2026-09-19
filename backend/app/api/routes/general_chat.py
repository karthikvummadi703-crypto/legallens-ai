from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.services.ai.general_chat_service import GeneralChatResponse, GeneralChatService
from app.utils.security import get_current_user

router = APIRouter(prefix="/chat", tags=["general-chat"])


class GeneralChatRequest(BaseModel):
    question: str = Field(
        ..., description="General legal question for LegalLens (no document required)"
    )
    conversation_id: str | None = Field(
        default=None, description="Optional ongoing conversation ID"
    )


class UnifiedChatRequest(BaseModel):
    question: str = Field(..., description="User question - may reference any owned document")
    conversation_id: str | None = Field(
        default=None, description="Optional ongoing conversation ID"
    )
    selected_document_id: str | None = Field(
        default=None, description="Currently selected document if any (for context)"
    )
    chat_id: str | None = Field(
        default=None, description="Frontend chat session id (ignored for auth, for logging only)"
    )


@router.post("/query", response_model=GeneralChatResponse)
async def unified_chat(body: UnifiedChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Unified ChatGPT-style endpoint.
    - Mode 1 (no doc): fast general legal chatbot — no Qdrant, pure Gemini + fallback.
    - Mode 2 (doc selected): strict document-grounded analyst — only selected doc unless
      the question explicitly references another owned doc (cross-doc signal).
    - NEVER trusts frontend user_id for ownership (uses verified Firebase token).
    """
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question string cannot be empty.")
    logger.info(
        f"Unified chat req: user='{current_user['uid'][:8]}...' sel_doc='{body.selected_document_id}' conv='{body.conversation_id}' q='{body.question[:60]}'"
    )
    try:
        # If a selected doc is provided, verify ownership before delegating
        sel_id = body.selected_document_id.strip() if body.selected_document_id else None
        sel_name = None
        if sel_id:
            from app.services.document_service import DocumentManager

            entry = DocumentManager.get_document_by_id(sel_id, current_user["uid"])
            if entry:
                sel_name = entry.get("metadata", {}).get("name", sel_id)
            else:
                logger.warning(
                    f"Unified chat: selected doc '{sel_id}' not owned by user '{current_user['uid'][:8]}...'"
                )
                sel_id = None

        # MODE 1: No document selected → pure general legal assistant (no Qdrant)
        if not sel_id:
            response = await GeneralChatService.ask_pure_general(
                question=body.question.strip(),
                user_id=current_user["uid"],
                conversation_id=body.conversation_id,
            )
            return response

        # MODE 2: Document selected → strict per-document RAG
        from app.services.ai.rag_service import RAGService

        response = await RAGService.ask_question(
            user_id=current_user["uid"],
            document_id=sel_id,
            document_name=sel_name or sel_id,
            question=body.question.strip(),
            conversation_id=body.conversation_id,
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified chat pipeline error: {e}")
        raise HTTPException(
            status_code=500, detail="LegalLens couldn't answer right now. Please try again."
        )


@router.post("", response_model=GeneralChatResponse)
async def general_chat(body: GeneralChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Document-independent LegalLens assistant.
    Answers general legal-information questions via Gemini without requiring an uploaded document.
    Kept for backward compatibility; prefer POST /api/chat/query for new clients.
    """
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question string cannot be empty.")

    try:
        response = await GeneralChatService.ask_question(
            question=body.question.strip(),
            user_id=current_user["uid"],
            conversation_id=body.conversation_id,
        )
        return response
    except Exception as e:
        logger.error(f"General chat pipeline error: {e}")
        raise HTTPException(
            status_code=500, detail="LegalLens couldn't answer right now. Please try again."
        )


@router.get("/conversations")
def list_chats(current_user: dict = Depends(get_current_user)):
    """
    List the authenticated user's library-wide and document chats
    (most recent first) for the sidebar.
    """
    from app.services.ai.rag_service import RAGService

    return {"conversations": RAGService.list_user_conversations(current_user["uid"])}


@router.get("/history")
def get_chat_history(
    conversation_id: str | None = None, current_user: dict = Depends(get_current_user)
):
    """
    Load message history for one library-wide conversation.
    Without an id, returns the most recent library-wide chat
    (document chats are never mixed into the general panel).
    """
    from app.services.ai.rag_service import RAGService

    user_id = current_user["uid"]
    if conversation_id:
        messages = RAGService.get_conversation_history(user_id, None, conversation_id)
        return {"conversation_id": conversation_id, "messages": messages}
    for convo in RAGService.list_user_conversations(user_id):
        if convo.get("document_id") is None:
            messages = RAGService.get_conversation_history(user_id, None, convo["conversation_id"])
            return {"conversation_id": convo["conversation_id"], "messages": messages}
    return {"conversation_id": None, "messages": []}

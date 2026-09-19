from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.services.ai.rag_service import RAGAnswerResponse, RAGService
from app.services.document_service import DocumentManager
from app.utils.security import get_current_user

router = APIRouter(prefix="/documents", tags=["chat"])


class ChatQuestionRequest(BaseModel):
    question: str = Field(..., description="Document-specific question to ask LegalLens RAG")
    conversation_id: str | None = Field(
        default=None, description="Optional ongoing conversation ID"
    )


@router.post("/{document_id}/chat", response_model=RAGAnswerResponse)
async def chat_with_document(
    document_id: str, body: ChatQuestionRequest, current_user: dict = Depends(get_current_user)
):
    """
    Execute Phase 4 RAG (Retrieval-Augmented Generation) Question & Answer pipeline.
    Retrieves top semantic vector chunks matching the question, enforces user & document ownership filtering,
    generates grounded answer with source page citations using Gemini API.
    """
    user_id = current_user["uid"]
    entry = DocumentManager.get_document_by_id(document_id, user_id)
    if not entry:
        raise HTTPException(
            status_code=404, detail=f"Document '{document_id}' not found or access denied."
        )

    doc_meta = entry.get("metadata", {})
    doc_name = doc_meta.get("name", "Document")

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question string cannot be empty.")

    try:
        response = await RAGService.ask_question(
            user_id=user_id,
            document_id=document_id,
            document_name=doc_name,
            question=body.question.strip(),
            conversation_id=body.conversation_id,
        )
        return response
    except Exception as e:
        logger.error(f"Chat pipeline error for doc '{document_id}': {e}")
        raise HTTPException(
            status_code=500,
            detail="LegalLens couldn't retrieve information from this document right now. Please try again.",
        )


@router.get("/{document_id}/conversations")
def get_document_conversations(
    document_id: str,
    conversation_id: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieve conversation history tied to authenticated user and specified document.
    """
    user_id = current_user["uid"]
    entry = DocumentManager.get_document_by_id(document_id, user_id)
    if not entry:
        raise HTTPException(
            status_code=404, detail=f"Document '{document_id}' not found or access denied."
        )

    messages = RAGService.get_conversation_history(user_id, document_id, conversation_id)
    return {"document_id": document_id, "messages": messages}


@router.post("/{document_id}/reindex")
def reindex_document_vectors(document_id: str, current_user: dict = Depends(get_current_user)):
    """
    Purge old vectors, re-chunk document text, generate embeddings, and reindex in Qdrant.
    """
    user_id = current_user["uid"]
    entry = DocumentManager.get_document_by_id(document_id, user_id)
    if not entry:
        raise HTTPException(
            status_code=404, detail=f"Document '{document_id}' not found or access denied."
        )

    try:
        success = DocumentManager.reindex_document(document_id, user_id)
        return {"status": "success", "indexed": success, "document_id": document_id}
    except Exception as e:
        logger.error(f"Reindexing failed for {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Document reindexing failed.")

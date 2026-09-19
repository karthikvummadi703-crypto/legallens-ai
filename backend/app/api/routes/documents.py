from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from typing import List, Optional
from pydantic import BaseModel, Field
from app.utils.security import get_current_user
from app.utils.file_utils import validate_uploaded_file
from app.models.document import DocumentMetadataResponse
from app.services.document_service import DocumentManager
from app.services.ai.schemas import FullDocumentAnalysis, DocumentComparison, ChecklistItemData
from app.services.ai.comparison_service import ComparisonService
from app.core.logging import logger

router = APIRouter(prefix="/documents", tags=["documents"])

class CompareRequest(BaseModel):
    document_a_id: str = Field(..., description="ID of the first (original) document")
    document_b_id: str = Field(..., description="ID of the second (revised) document")

@router.post("/compare", response_model=DocumentComparison)
async def compare_documents(
    body: CompareRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Compare two user-owned contracts side by side.
    Returns Added / Removed / Changed / Unchanged clause differences with
    plain-language explanations and summary counters.
    """
    user_id = current_user["uid"]
    if not body.document_a_id.strip() or not body.document_b_id.strip():
        raise HTTPException(status_code=400, detail="Both document_a_id and document_b_id are required.")
    try:
        return await ComparisonService.compare_documents(
            user_id, body.document_a_id.strip(), body.document_b_id.strip()
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Comparison failed for '{body.document_a_id}' vs '{body.document_b_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to compare documents. Please try again.")

@router.get("/{document_id}/checklist", response_model=List[ChecklistItemData])
def get_document_checklist(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Build an actionable pre-signing checklist from the stored analysis.
    Returns an empty list when the document has not been analyzed yet.
    """
    user_id = current_user["uid"]
    entry = DocumentManager.get_document_by_id(document_id, user_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or access denied.")
    return DocumentManager.get_document_checklist(document_id, user_id)

@router.post("/upload", response_model=DocumentMetadataResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a legal document (PDF, DOCX, TXT).
    Processes page-aware text extraction, detects sections & preliminary clauses,
    stores metadata, and returns the uploaded document metadata.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a valid filename.")

    try:
        content = await file.read()
        # Centralized validation: extension, size, and magic-byte content check
        validate_uploaded_file(file, content)

        user_id = current_user["uid"]
        doc_meta = await DocumentManager.process_and_save_upload(file, content, user_id)
        return doc_meta
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while extracting and saving the document.")

@router.get("", response_model=List[DocumentMetadataResponse])
def get_user_documents(current_user: dict = Depends(get_current_user)):
    """
    Retrieve all legal documents belonging to the authenticated user.
    """
    user_id = current_user["uid"]
    return DocumentManager.get_user_documents(user_id)

@router.get("/{document_id}")
def get_document_details(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve full extracted document content and metadata by ID.
    Enforces document ownership.
    """
    user_id = current_user["uid"]
    entry = DocumentManager.get_document_by_id(document_id, user_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or access denied.")
    # Strip server-internal fields from the response
    safe_entry = {
        k: v for k, v in entry.items() if k not in ("saved_path",)
    }
    return safe_entry

@router.post("/{document_id}/analyze", response_model=FullDocumentAnalysis)
async def analyze_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute Phase 3 Gemini Legal Intelligence pipeline for the specified document.
    Returns structured, grounded, Pydantic-validated insights.
    """
    user_id = current_user["uid"]
    entry = DocumentManager.get_document_by_id(document_id, user_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or access denied.")

    try:
        analysis = await DocumentManager.analyze_document(document_id, user_id)
        return analysis
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Analysis failed for {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to run document analysis. Please try again.")

@router.get("/{document_id}/analysis", response_model=FullDocumentAnalysis)
def get_document_analysis(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve previously stored analysis result for a document.
    """
    user_id = current_user["uid"]
    entry = DocumentManager.get_document_by_id(document_id, user_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or access denied.")

    analysis = DocumentManager.get_document_analysis(document_id, user_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis for document '{document_id}' has not been run yet.")
    return analysis

@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a document and its stored analysis records.
    """
    user_id = current_user["uid"]
    success = DocumentManager.delete_document(document_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or access denied.")
    return {"status": "success", "message": f"Document '{document_id}' deleted successfully."}

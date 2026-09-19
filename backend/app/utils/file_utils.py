import os
import re

from fastapi import HTTPException, UploadFile

from app.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".log"}

# Extensions read as plain text (no magic-byte signature to verify).
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".log"}


def validate_uploaded_file(file: UploadFile, content_bytes: bytes) -> str:
    """
    Validate uploaded file extension, size, and magic-byte content signature.
    Any readable document type is accepted (not only legal files).
    Returns the file extension string.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted types: PDF, DOCX, TXT, MD, CSV, HTML, LOG.",
        )

    if len(content_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content_bytes) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of 20MB (uploaded: {len(content_bytes) / (1024 * 1024):.2f}MB).",
        )

    # Magic-byte content signature validation
    if ext == ".pdf" and not content_bytes.lstrip()[:5].startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail="File extension is .pdf but content does not appear to be a valid PDF.",
        )

    if ext == ".docx" and not content_bytes[:4] == b"PK\x03\x04":
        raise HTTPException(
            status_code=400,
            detail="File extension is .docx but content does not appear to be a valid DOCX archive.",
        )

    return ext


def sanitize_filename(filename: str) -> str:
    """Remove characters unsafe for filesystem paths; prevents directory traversal."""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\. ]", "_", filename)
    cleaned = cleaned.strip()
    # Prevent traversal tokens
    cleaned = cleaned.replace("..", "_")
    if cleaned in (".", "..", ""):
        cleaned = "document"
    return cleaned[:100]

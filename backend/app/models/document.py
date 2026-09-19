from pydantic import BaseModel


class PageContent(BaseModel):
    page_number: int
    text: str
    character_count: int


class DocumentSection(BaseModel):
    title: str
    start_page: int
    end_page: int
    content: str


class DocumentClause(BaseModel):
    clause_id: str
    title: str
    page: int
    section: str
    text: str


class ExtractedDocument(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    total_pages: int
    pages: list[PageContent]
    sections: list[DocumentSection]
    clauses: list[DocumentClause]
    full_text: str


class DocumentMetadataResponse(BaseModel):
    id: str
    name: str
    type: str
    uploadDate: str
    size: str
    analysisStatus: str
    indexingStatus: str | None = "indexed"
    attentionScore: int
    pageCount: int
    category: str
    summary: str | None = ""
    clausesCount: int = 0
    risksCount: int = 0
    obligationsCount: int = 0

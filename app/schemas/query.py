from pydantic import BaseModel, Field
from uuid import UUID


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: UUID | None = None
    conversation_id: UUID | None = None
    k: int = Field(default=5, ge=1, le=20)


class Source(BaseModel):
    chunk_id: str
    content: str
    page: int
    bboxes: list[list[float]] | None = None
    page_width: int | None = None
    page_height: int | None = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    has_answer: bool
    sources: list[Source]
    conversation_id: UUID | None = None
from typing import Literal

from pydantic import BaseModel, Field
from uuid import UUID


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: UUID | None = None
    conversation_id: UUID | None = None
    k: int = Field(default=5, ge=1, le=20)


class Source(BaseModel):
    source_type: Literal["document", "web"] = "document"
    chunk_id: str | None = None
    content: str
    page: int | None = None
    bboxes: list[list[float]] | None = None
    page_width: int | None = None
    page_height: int | None = None
    url: str | None = None
    title: str | None = None
    provider: Literal["wikipedia", "duckduckgo"] | None = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    has_answer: bool
    sources: list[Source]
    conversation_id: UUID | None = None
from pydantic import BaseModel, Field
from uuid import UUID


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: UUID | None = None
    k: int = Field(default=5, ge=1, le=20)


class Source(BaseModel):
    content: str
    page: int


class QueryResponse(BaseModel):
    question: str
    answer: str
    has_answer: bool  # False when the LLM couldn't answer from the context
    sources: list[Source]
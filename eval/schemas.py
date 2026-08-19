"""Shared eval dataset schemas."""

from pydantic import BaseModel, Field


class EvalItem(BaseModel):
    question: str
    expected_answer: str
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    document_id: str | None = None
    difficulty: str = "medium"
    expected_tools: list[str] = Field(default_factory=lambda: ["search_documents"])
    expect_has_answer: bool = True


class EvalItemBatch(BaseModel):
    items: list[EvalItem]

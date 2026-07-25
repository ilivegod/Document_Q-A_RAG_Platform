from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.query import Source


class AgentStep(BaseModel):
    tool: str
    input: dict
    output_summary: str


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: UUID | None = None
    project_id: UUID | None = None
    conversation_id: UUID | None = None
    stream: bool = False


class AgentQueryResponse(BaseModel):
    question: str
    answer: str
    has_answer: bool
    sources: list[Source]
    conversation_id: UUID | None = None
    agent_steps: list[AgentStep] = []

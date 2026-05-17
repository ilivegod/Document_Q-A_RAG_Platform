from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Any


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    document_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    sources: list[Any] | None = None
    has_answer: bool | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
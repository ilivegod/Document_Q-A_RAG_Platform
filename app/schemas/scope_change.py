from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScopeChangeSubmit(BaseModel):
    description: str = Field(min_length=10, max_length=4000)
    passcode: str | None = None


class ScopeChangeResponse(BaseModel):
    id: UUID
    project_id: UUID
    client_description: str
    ai_is_out_of_scope: bool
    ai_reasoning: str
    estimated_hours: Decimal | None = None
    estimated_cost: Decimal | None = None
    status: str
    linked_task_id: UUID | None = None
    linked_requirement_id: UUID | None = None
    created_at: datetime
    reviewed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ScopeChangeDecide(BaseModel):
    action: str = Field(
        description="approve_change_order, reject, or convert_to_task"
    )


class ScopeChangeSubmitResponse(BaseModel):
    id: UUID
    status: str
    ai_is_out_of_scope: bool
    ai_reasoning: str
    estimated_hours: Decimal | None = None
    estimated_cost: Decimal | None = None
    message: str

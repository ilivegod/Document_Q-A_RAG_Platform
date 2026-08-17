"""Unit tests for scope change review actions."""
import uuid

import pytest

from app.models.scope_change_request import ScopeChangeRequest, ScopeChangeStatus
from app.models.task import Task
from app.services.scope_change import decide_scope_change


class FakeSession:
    def __init__(self):
        self.added = []

    async def get(self, model, id):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.mark.asyncio
async def test_convert_scope_change_to_task():
    from unittest.mock import AsyncMock, patch

    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    request_id = uuid.uuid4()

    row = ScopeChangeRequest(
        id=request_id,
        project_id=project_id,
        client_description="Add export to CSV",
        ai_is_out_of_scope=True,
        ai_reasoning="Not in original scope",
        estimated_hours=8,
        estimated_cost=800,
        status=ScopeChangeStatus.PENDING_REVIEW,
    )

    class Session(FakeSession):
        async def get(self, model, id):
            if model is ScopeChangeRequest and id == request_id:
                return row
            return None

    db = Session()
    with patch(
        "app.services.scope_change.get_project_or_404",
        new_callable=AsyncMock,
    ):
        result = await decide_scope_change(
            db,
            user_id,
            project_id,
            request_id,
            "convert_to_task",
        )
    assert result.status == ScopeChangeStatus.CONVERTED_TO_TASK
    assert result.linked_task_id is not None
    assert any(isinstance(obj, Task) for obj in db.added)

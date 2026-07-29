"""Unit tests for delivery health scoring and replan apply."""
import uuid
from types import SimpleNamespace

import pytest

from app.models.milestone import MilestoneStatus
from app.models.plan_proposal import PlanProposal, ProposalStatus, ProposalType
from app.models.requirement import RequirementStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.services.delivery_health import compute_delivery_health
from app.services.project_checkin import apply_replan_proposal


def _task(*, status: TaskStatus, requirement_id=None, title="Task"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        requirement_id=requirement_id,
        title=title,
        sort_order=0,
    )


def _req(*, status: RequirementStatus, req_id=None):
    return SimpleNamespace(
        id=req_id or uuid.uuid4(),
        status=status,
        title="Req",
    )


def _milestone(*, status: MilestoneStatus = MilestoneStatus.ACTIVE):
    return SimpleNamespace(status=status, title="M")


def test_compute_delivery_health_not_started():
    health = compute_delivery_health(
        tasks=[],
        milestones=[],
        requirements=[],
        open_questions=[],
    )
    assert health.level == "not_started"
    assert health.score == 0
    assert health.task_counts["total"] == 0


def test_compute_delivery_health_penalizes_blockers():
    req_id = uuid.uuid4()
    health = compute_delivery_health(
        tasks=[
            _task(status=TaskStatus.BLOCKED, requirement_id=req_id),
            _task(status=TaskStatus.BLOCKED),
            _task(status=TaskStatus.NEXT),
        ],
        milestones=[_milestone()],
        requirements=[_req(status=RequirementStatus.CONFIRMED, req_id=req_id)],
        open_questions=[],
    )
    assert health.blocked_count == 2
    assert health.level in {"at_risk", "critical"}
    assert any("blocked" in signal for signal in health.signals)


def test_compute_delivery_health_healthy_progress():
    req_a = uuid.uuid4()
    req_b = uuid.uuid4()
    health = compute_delivery_health(
        tasks=[
            _task(status=TaskStatus.NOW, requirement_id=req_a),
            _task(status=TaskStatus.DONE, requirement_id=req_b),
            _task(status=TaskStatus.DONE),
            _task(status=TaskStatus.NEXT),
        ],
        milestones=[_milestone()],
        requirements=[
            _req(status=RequirementStatus.CONFIRMED, req_id=req_a),
            _req(status=RequirementStatus.CONFIRMED, req_id=req_b),
        ],
        open_questions=[],
    )
    assert health.score >= 75
    assert health.level == "healthy"
    assert health.requirement_coverage == 1.0


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, tasks):
        self.tasks = tasks
        self.added = []

    async def execute(self, _stmt):
        return FakeResult(self.tasks)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Task) and obj.id is None:
            obj.id = uuid.uuid4()
            self.tasks.append(obj)


@pytest.mark.asyncio
async def test_apply_replan_updates_and_creates_tasks():
    project_id = uuid.uuid4()
    existing = Task(
        id=uuid.uuid4(),
        project_id=project_id,
        title="Old focus",
        status=TaskStatus.NEXT,
        priority=TaskPriority.SHOULD,
        sort_order=0,
    )
    db = FakeSession([existing])
    proposal = PlanProposal(
        id=uuid.uuid4(),
        project_id=project_id,
        proposal_type=ProposalType.REPLAN,
        status=ProposalStatus.PENDING,
        title="Rebalance",
        summary="Move focus",
        payload={
            "task_updates": [
                {
                    "task_id": str(existing.id),
                    "status": "now",
                    "priority": "must",
                    "title": "Active focus",
                }
            ],
            "new_tasks": [
                {
                    "title": "Unblock API keys",
                    "status": "blocked",
                    "priority": "must",
                    "blocker_reason": "Waiting on vendor",
                }
            ],
        },
    )

    result = await apply_replan_proposal(db, project_id, proposal)

    assert result["tasks_updated"] == 1
    assert result["tasks_created"] == 1
    assert existing.status == TaskStatus.NOW
    assert existing.priority == TaskPriority.MUST
    assert existing.title == "Active focus"
    created = [obj for obj in db.added if isinstance(obj, Task)][0]
    assert created.title == "Unblock API keys"
    assert created.status == TaskStatus.BLOCKED
    assert created.blocker_reason == "Waiting on vendor"

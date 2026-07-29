"""Unit tests for applying approved work-breakdown proposals."""
import uuid

import pytest

from app.models.milestone import Milestone
from app.models.plan_proposal import PlanProposal, ProposalStatus, ProposalType
from app.models.requirement import Requirement, RequirementCategory, RequirementStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.services.work_breakdown import (
    WorkBreakdownResult,
    ProposedMilestone,
    ProposedTask,
    apply_work_breakdown_proposal,
    build_work_breakdown_payload,
)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self):
        self.added = []
        self.milestones = []
        self.tasks = []
        self.activity = []

    async def execute(self, _stmt):
        # list_milestones / list_tasks / list_working_requirements call execute.
        # We only need empty existing plan for apply tests that pass requirement map.
        return FakeResult([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Milestone):
            if obj.id is None:
                obj.id = uuid.uuid4()
            self.milestones.append(obj)
        elif isinstance(obj, Task):
            if obj.id is None:
                obj.id = uuid.uuid4()
            self.tasks.append(obj)
        else:
            self.activity.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()


@pytest.mark.asyncio
async def test_apply_work_breakdown_creates_milestones_and_tasks():
    project_id = uuid.uuid4()
    req_id = uuid.uuid4()
    requirement = Requirement(
        id=req_id,
        project_id=project_id,
        stable_id="REQ-001",
        title="Auth",
        category=RequirementCategory.FEATURE,
        status=RequirementStatus.CONFIRMED,
    )

    result = WorkBreakdownResult(
        title="MVP plan",
        summary="Ship auth first",
        milestones=[
            ProposedMilestone(temp_id="m1", title="Foundation", description="Core"),
        ],
        tasks=[
            ProposedTask(
                temp_id="t1",
                title="Implement login",
                description="Email/password",
                priority="must",
                status="now",
                milestone_temp_id="m1",
                requirement_stable_ids=["REQ-001"],
                acceptance_criteria=["User can sign in"],
            ),
            ProposedTask(
                temp_id="t2",
                title="Add session refresh",
                priority="should",
                status="next",
                milestone_temp_id="m1",
            ),
        ],
    )

    proposal = PlanProposal(
        id=uuid.uuid4(),
        project_id=project_id,
        proposal_type=ProposalType.WORK_BREAKDOWN,
        status=ProposalStatus.APPROVED,
        title=result.title,
        summary=result.summary,
        payload=build_work_breakdown_payload(result),
    )

    db = FakeSession()
    counts = await apply_work_breakdown_proposal(
        db,
        project_id,
        proposal,
        requirement_by_stable_id={"REQ-001": requirement},
    )

    assert counts == {"milestones_created": 1, "tasks_created": 2}
    assert len(db.milestones) == 1
    assert db.milestones[0].title == "Foundation"
    assert len(db.tasks) == 2
    assert db.tasks[0].title == "Implement login"
    assert db.tasks[0].priority == TaskPriority.MUST
    assert db.tasks[0].status == TaskStatus.NOW
    assert db.tasks[0].requirement_id == req_id
    assert db.tasks[0].milestone_id == db.milestones[0].id
    assert db.tasks[0].acceptance_criteria == ["User can sign in"]
    assert any(
        getattr(item, "event_type", None) == "proposal.applied"
        for item in db.activity
    )

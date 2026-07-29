"""Unit tests for delivery helpers: QA seeding, changelog, status recompute."""
import uuid
from types import SimpleNamespace

from app.models.qa_run import QaCheckItem, QaItemStatus, QaRun, QaRunStatus
from app.models.requirement import RequirementStatus
from app.models.task import TaskPriority, TaskStatus
from app.services.delivery import (
    build_changelog,
    recompute_qa_run_status,
    seed_items_from_requirements,
)


def test_seed_items_from_acceptance_criteria():
    req = SimpleNamespace(
        id=uuid.uuid4(),
        stable_id="REQ-001",
        title="Auth",
        description="Users can sign in",
        status=RequirementStatus.CONFIRMED,
        acceptance_criteria=["Can log in", "Can log out"],
    )
    proposed = SimpleNamespace(
        id=uuid.uuid4(),
        stable_id="REQ-002",
        title="Skip me",
        description=None,
        status=RequirementStatus.PROPOSED,
        acceptance_criteria=["ignored"],
    )
    seeded = seed_items_from_requirements([req, proposed])
    assert len(seeded) == 2
    assert seeded[0][1] == "Can log in"
    assert seeded[1][1] == "Can log out"


def test_seed_items_falls_back_to_verify_title():
    req = SimpleNamespace(
        id=uuid.uuid4(),
        stable_id="REQ-010",
        title="Export CSV",
        description="Allow CSV export",
        status=RequirementStatus.CONFIRMED,
        acceptance_criteria=[],
    )
    seeded = seed_items_from_requirements([req])
    assert len(seeded) == 1
    assert seeded[0][1] == "Verify: Export CSV"


def test_build_changelog_only_done_tasks():
    tasks = [
        SimpleNamespace(
            id=uuid.uuid4(),
            title="Done task",
            status=TaskStatus.DONE,
            priority=TaskPriority.MUST,
            requirement_id=uuid.uuid4(),
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            title="Still open",
            status=TaskStatus.NOW,
            priority=TaskPriority.SHOULD,
            requirement_id=None,
        ),
    ]
    changelog = build_changelog(tasks)
    assert len(changelog) == 1
    assert changelog[0]["title"] == "Done task"


def test_recompute_qa_run_status_passed_and_failed():
    run = QaRun(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Acceptance",
        status=QaRunStatus.IN_PROGRESS,
    )
    items = [
        QaCheckItem(
            id=uuid.uuid4(),
            qa_run_id=run.id,
            title="A",
            status=QaItemStatus.PASSED,
            sort_order=0,
        ),
        QaCheckItem(
            id=uuid.uuid4(),
            qa_run_id=run.id,
            title="B",
            status=QaItemStatus.SKIPPED,
            sort_order=1,
        ),
    ]
    recompute_qa_run_status(run, items)
    assert run.status == QaRunStatus.PASSED
    assert run.completed_at is not None

    items[1].status = QaItemStatus.FAILED
    recompute_qa_run_status(run, items)
    assert run.status == QaRunStatus.FAILED

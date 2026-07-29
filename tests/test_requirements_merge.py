"""Unit tests for non-destructive requirements merge."""
import uuid

from app.models.requirement import Requirement, RequirementCategory, RequirementStatus
from app.services.requirements_merge import (
    ExtractedOpenQuestion,
    ExtractedRequirementItem,
    RequirementsExtractionResult,
    merge_extraction_into_requirements,
)


def _req(
    *,
    stable_id: str,
    title: str,
    status: RequirementStatus = RequirementStatus.PROPOSED,
    category: RequirementCategory = RequirementCategory.FEATURE,
    sort_order: int = 0,
) -> Requirement:
    return Requirement(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        stable_id=stable_id,
        title=title,
        description="old description",
        category=category,
        status=status,
        acceptance_criteria=["old"],
        assumptions=[],
        source_refs=[],
        sort_order=sort_order,
    )


def test_merge_adds_new_and_updates_proposed():
    project_id = uuid.uuid4()
    existing = [
        _req(stable_id="REQ-001", title="Login", sort_order=0),
    ]
    result = RequirementsExtractionResult(
        requirements=[
            ExtractedRequirementItem(
                stable_id="REQ-001",
                title="Login",
                description="Users can sign in",
                category="feature",
                priority="must",
                acceptance_criteria=["email + password"],
            ),
            ExtractedRequirementItem(
                stable_id="REQ-002",
                title="Dashboard",
                description="Show project overview",
                category="feature",
                priority="should",
            ),
        ]
    )

    added, updated, summary = merge_extraction_into_requirements(
        existing,
        result,
        project_id=project_id,
        chunks=[],
    )

    assert summary.added == 1
    assert summary.updated == 1
    assert summary.preserved == 0
    assert len(added) == 1
    assert added[0].stable_id == "REQ-002"
    assert updated[0].description == "Users can sign in"
    assert updated[0].acceptance_criteria == ["email + password"]


def test_merge_preserves_confirmed_and_rejected():
    project_id = uuid.uuid4()
    confirmed = _req(
        stable_id="REQ-001",
        title="Login",
        status=RequirementStatus.CONFIRMED,
        sort_order=0,
    )
    rejected = _req(
        stable_id="REQ-002",
        title="Dark mode",
        status=RequirementStatus.REJECTED,
        sort_order=1,
    )
    result = RequirementsExtractionResult(
        requirements=[
            ExtractedRequirementItem(
                stable_id="REQ-001",
                title="Login rewritten",
                description="Should not overwrite",
                category="feature",
                priority="must",
            ),
            ExtractedRequirementItem(
                stable_id="REQ-002",
                title="Dark mode rewritten",
                description="Should not overwrite",
                category="feature",
                priority="could",
            ),
        ]
    )

    added, updated, summary = merge_extraction_into_requirements(
        [confirmed, rejected],
        result,
        project_id=project_id,
        chunks=[],
    )

    assert summary.preserved == 2
    assert summary.added == 0
    assert summary.updated == 0
    assert added == []
    assert updated == []
    assert confirmed.title == "Login"
    assert confirmed.description == "old description"
    assert rejected.title == "Dark mode"


def test_merge_does_not_delete_missing_items():
    project_id = uuid.uuid4()
    existing = [
        _req(stable_id="REQ-001", title="Keep me", sort_order=0),
        _req(stable_id="REQ-002", title="Also keep", sort_order=1),
    ]
    result = RequirementsExtractionResult(
        requirements=[
            ExtractedRequirementItem(
                stable_id="REQ-003",
                title="Brand new",
                description="New item",
                category="feature",
            ),
        ]
    )

    added, updated, summary = merge_extraction_into_requirements(
        existing,
        result,
        project_id=project_id,
        chunks=[],
    )

    assert summary.added == 1
    assert summary.updated == 0
    assert len(existing) == 2
    assert {r.stable_id for r in existing} == {"REQ-001", "REQ-002"}
    assert added[0].stable_id == "REQ-003"
    assert updated == []


def test_merge_preserves_resolved_open_questions():
    project_id = uuid.uuid4()
    resolved = _req(
        stable_id="Q-001",
        title="Who is the admin?",
        status=RequirementStatus.CONFIRMED,
        category=RequirementCategory.OPEN_QUESTION,
        sort_order=0,
    )
    result = RequirementsExtractionResult(
        open_questions=[
            ExtractedOpenQuestion(
                title="Who is the admin?",
                description="Should not overwrite resolved question",
            ),
            ExtractedOpenQuestion(
                title="What is the deadline?",
                description="New unresolved question",
            ),
        ]
    )

    added, updated, summary = merge_extraction_into_requirements(
        [resolved],
        result,
        project_id=project_id,
        chunks=[],
    )

    assert summary.preserved == 1
    assert summary.added == 1
    assert summary.updated == 0
    assert resolved.description == "old description"
    assert added[0].stable_id == "Q-002"
    assert added[0].status == RequirementStatus.PROPOSED

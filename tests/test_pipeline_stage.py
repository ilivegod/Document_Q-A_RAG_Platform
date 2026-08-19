"""Unit tests for agency pipeline stage transitions."""

from uuid import uuid4

from app.models.project import PipelineStage, Project, ProjectStatus, ProjectType
from app.services.pipeline_stage import (
    advance_pipeline_stage,
    advance_to_handed_off,
    advance_to_qa_review,
)


def _project(stage: PipelineStage) -> Project:
    return Project(
        name="Test",
        user_id=uuid4(),
        project_type=ProjectType.CLIENT,
        status=ProjectStatus.ACTIVE,
        pipeline_stage=stage,
    )


def test_advance_pipeline_stage_moves_forward_only():
    project = _project(PipelineStage.IN_DEVELOPMENT)
    assert advance_pipeline_stage(project, PipelineStage.QA_REVIEW) is True
    assert project.pipeline_stage == PipelineStage.QA_REVIEW
    assert advance_pipeline_stage(project, PipelineStage.IN_DEVELOPMENT) is False
    assert project.pipeline_stage == PipelineStage.QA_REVIEW


def test_advance_to_qa_review_from_proposal_sent():
    project = _project(PipelineStage.PROPOSAL_SENT)
    assert advance_to_qa_review(project) is True
    assert project.pipeline_stage == PipelineStage.QA_REVIEW


def test_advance_to_handed_off_from_qa_review():
    project = _project(PipelineStage.QA_REVIEW)
    assert advance_to_handed_off(project) is True
    assert project.pipeline_stage == PipelineStage.HANDED_OFF


def test_advance_to_handed_off_skips_when_already_handed_off():
    project = _project(PipelineStage.HANDED_OFF)
    assert advance_to_handed_off(project) is False
    assert project.pipeline_stage == PipelineStage.HANDED_OFF

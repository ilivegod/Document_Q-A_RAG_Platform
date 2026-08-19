"""Agency pipeline stage ordering and safe forward transitions."""

from __future__ import annotations

from app.models.project import PipelineStage, Project

_PIPELINE_ORDER: list[PipelineStage] = [
    PipelineStage.LEAD,
    PipelineStage.PROPOSAL_SENT,
    PipelineStage.IN_DEVELOPMENT,
    PipelineStage.QA_REVIEW,
    PipelineStage.HANDED_OFF,
]


def _stage_index(stage: PipelineStage) -> int:
    return _PIPELINE_ORDER.index(stage)


def advance_pipeline_stage(project: Project, target: PipelineStage) -> bool:
    """Move pipeline_stage forward only; returns True if changed."""
    current_idx = _stage_index(project.pipeline_stage)
    target_idx = _stage_index(target)
    if target_idx > current_idx:
        project.pipeline_stage = target
        return True
    return False


def advance_to_qa_review(project: Project) -> bool:
    return advance_pipeline_stage(project, PipelineStage.QA_REVIEW)


def advance_to_handed_off(project: Project) -> bool:
    return advance_pipeline_stage(project, PipelineStage.HANDED_OFF)

"""Post-upload project analysis: requirements extraction + technology suggestions."""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.services.requirements_extractor import extract_requirements_for_project
from app.services.technology_explorer import suggest_initial_explorations

logger = logging.getLogger(__name__)


async def _set_analysis_status(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    analyzing: bool,
    requirements_extracted: bool | None = None,
    technology_suggested: bool | None = None,
) -> None:
    """Update project analysis fields when the migration is present."""
    from app.models.project import Project

    project = await db.get(Project, project_id)
    if project is None:
        return

    from app.models.project import ProjectAnalysisStatus

    project.analysis_status = (
        ProjectAnalysisStatus.RUNNING if analyzing else ProjectAnalysisStatus.COMPLETE
    )
    if requirements_extracted is not None:
        project.requirements_extracted = requirements_extracted
    if technology_suggested is not None:
        project.technology_suggested = technology_suggested
    if not analyzing:
        project.last_analyzed_at = datetime.now(timezone.utc)
    await db.commit()


async def run_project_analysis(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Extract requirements and suggest technology options for a project."""
    await _set_analysis_status(db, project_id, analyzing=True)

    requirements_ok = False
    technology_ok = False

    try:
        await extract_requirements_for_project(db, user_id, project_id)
        requirements_ok = True
        logger.info("Project %s: requirements extracted", project_id)
    except HTTPException as e:
        logger.warning(
            "Project %s: requirements extraction skipped: %s", project_id, e.detail
        )
    except Exception as e:
        logger.error(
            "Project %s: requirements extraction failed: %s",
            project_id,
            e,
            exc_info=True,
        )

    try:
        explorations = await suggest_initial_explorations(db, user_id, project_id)
        technology_ok = len(explorations) > 0
        logger.info(
            "Project %s: %d technology exploration(s) created",
            project_id,
            len(explorations),
        )
    except Exception as e:
        logger.error(
            "Project %s: technology suggestions failed: %s",
            project_id,
            e,
            exc_info=True,
        )

    await _set_analysis_status(
        db,
        project_id,
        analyzing=False,
        requirements_extracted=requirements_ok,
        technology_suggested=technology_ok,
    )


async def auto_analyze_project(
    document_id: str,
    project_id: str,
    user_id: str,
) -> None:
    """Celery entrypoint: analyze project after a document reaches READY."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
            logger.info(
                "Auto-analyzing project %s after document %s",
                project_id,
                document_id,
            )
            await run_project_analysis(
                db,
                uuid.UUID(user_id),
                uuid.UUID(project_id),
            )
    finally:
        await engine.dispose()

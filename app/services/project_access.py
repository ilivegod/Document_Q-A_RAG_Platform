from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.project import Project


async def get_project_or_404(
    project_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Project:
    project = await db.get(Project, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def get_document_in_project_or_404(
    project_id: UUID,
    document_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Document:
    await get_project_or_404(project_id, user_id, db)
    doc = await db.get(Document, document_id)
    if doc is None or doc.user_id != user_id or doc.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

"""Create text/markdown project documents and enqueue embedding."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document
from app.services.storage import make_storage_key, upload_file
from app.workers.tasks import process_document_task

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


async def create_text_document_for_project(
    db: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    file_name: str,
    content: str,
    extension: str = ".md",
) -> Document:
    """Write text content to storage, create Document row, enqueue embed pipeline."""
    if extension not in {".md", ".txt", ".markdown"}:
        extension = ".md"

    doc_id = uuid.uuid4()
    unique_filename = f"{doc_id}{extension}"
    temp_path = UPLOAD_DIR / unique_filename
    temp_path.write_text(content, encoding="utf-8")

    if settings.r2_bucket_name:
        storage_key = make_storage_key(str(user_id), str(doc_id), extension)
        await upload_file(str(temp_path), storage_key)
        temp_path.unlink(missing_ok=True)
        stored_path = storage_key
    else:
        stored_path = str(temp_path)

    doc = Document(
        id=doc_id,
        user_id=user_id,
        project_id=project_id,
        file_name=file_name,
        file_type=extension,
        file_path=stored_path,
    )
    db.add(doc)
    await db.flush()

    process_document_task.delay(str(doc.id))
    logger.info("Created text document %s for project %s", doc.id, project_id)
    return doc

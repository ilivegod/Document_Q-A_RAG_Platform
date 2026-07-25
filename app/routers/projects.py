import logging
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.getUser import get_current_user
from app.dependencies.rate_limit import UPLOAD_LIMIT, get_user_id_key, limiter
from app.models.document import Document
from app.models.project import Project, ProjectAnalysisStatus
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, ProjectAnalysisStatusResponse
from app.services.project_access import (
    get_document_in_project_or_404,
    get_project_or_404,
)
from app.services.storage import delete_file, make_storage_key, upload_file
from app.workers.tasks import process_document_task

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_to_response(project: Project, document_count: int) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        client_name=project.client_name,
        project_type=project.project_type,
        status=project.status,
        document_count=document_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def _document_count(db: AsyncSession, project_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Document)
        .where(Document.project_id == project_id)
    )
    return int(result.scalar_one())


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()
    responses: list[ProjectResponse] = []
    for project in projects:
        count = await _document_count(db, project.id)
        responses.append(_project_to_response(project, count))
    return responses


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        client_name=body.client_name,
        project_type=body.project_type,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _project_to_response(project, 0)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, current_user.id, db)
    count = await _document_count(db, project.id)
    return _project_to_response(project, count)


@router.get("/{project_id}/analysis-status", response_model=ProjectAnalysisStatusResponse)
async def get_project_analysis_status(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, current_user.id, db)
    return ProjectAnalysisStatusResponse(
        analysis_status=project.analysis_status,
        requirements_extracted=project.requirements_extracted,
        technology_generated=project.technology_generated,
        analyzing=project.analysis_status == ProjectAnalysisStatus.RUNNING,
        last_analyzed_at=project.last_analyzed_at,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, current_user.id, db)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    count = await _document_count(db, project.id)
    return _project_to_response(project, count)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, current_user.id, db)
    await db.delete(project)
    await db.commit()
    return None


@router.get("/{project_id}/documents")
async def list_project_documents(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)
    result = await db.execute(
        select(Document)
        .where(
            Document.project_id == project_id,
            Document.user_id == current_user.id,
        )
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{project_id}/documents/upload")
@limiter.limit(UPLOAD_LIMIT, key_func=get_user_id_key)
async def upload_project_document(
    request: Request,
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await get_project_or_404(project_id, current_user.id, db)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF/DOCX allowed."
        )

    doc_id = uuid.uuid4()
    unique_filename = f"{doc_id}{file_extension}"
    temp_path = UPLOAD_DIR / unique_filename

    total_bytes = 0
    try:
        with temp_path.open("wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    f.close()
                    temp_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Max size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        logger.error(f"Failed to save file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save file")

    if total_bytes == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if settings.r2_bucket_name:
        storage_key = make_storage_key(
            str(current_user.id), str(doc_id), file_extension
        )
        try:
            await upload_file(str(temp_path), storage_key)
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            logger.error(f"R2 upload failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Could not store file")
        finally:
            temp_path.unlink(missing_ok=True)
        stored_path = storage_key
    else:
        stored_path = str(temp_path)

    db_record = Document(
        id=doc_id,
        user_id=current_user.id,
        project_id=project_id,
        file_name=file.filename,
        file_type=file_extension,
        file_path=stored_path,
    )
    db.add(db_record)
    await db.commit()

    doc_id_str = str(db_record.id)
    logger.info(f"Dispatching processing task for document {doc_id_str}")
    process_document_task.delay(doc_id_str)

    return {"id": doc_id_str, "status": db_record.status, "project_id": str(project_id)}


@router.get("/{project_id}/documents/{document_id}")
async def get_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await get_document_in_project_or_404(
        project_id, document_id, current_user.id, db
    )
    chunk_count_result = await db.execute(
        text("SELECT COUNT(*) FROM chunk WHERE doc_id = :doc_id"),
        {"doc_id": str(doc.id)},
    )
    chunk_count = chunk_count_result.scalar_one()
    return {
        "id": str(doc.id),
        "user_id": str(doc.user_id),
        "project_id": str(doc.project_id),
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "status": doc.status,
        "created_at": doc.created_at,
        "chunk_count": chunk_count,
    }


@router.delete("/{project_id}/documents/{document_id}")
async def delete_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await get_document_in_project_or_404(
        project_id, document_id, current_user.id, db
    )

    await db.execute(
        text("DELETE FROM chunk WHERE doc_id = :doc_id"),
        {"doc_id": str(document_id)},
    )

    if settings.r2_bucket_name:
        await delete_file(doc.file_path)
    else:
        local = Path(doc.file_path)
        if local.exists():
            local.unlink()

    await db.delete(doc)
    await db.commit()
    return {"detail": "Document deleted"}

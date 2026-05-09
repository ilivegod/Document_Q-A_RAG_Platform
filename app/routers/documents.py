from fastapi import (
    UploadFile,
    File,
    HTTPException,
    APIRouter,
    Depends,
    Request,
    status,
)
from pathlib import Path
import uuid
import logging

from app.models.document import Document
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.user import User
from app.dependencies.getUser import get_current_user
from app.workers.tasks import process_document_task
from app.dependencies.rate_limit import limiter, get_user_id_key, UPLOAD_LIMIT

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB


router = APIRouter()


@router.get("/documents")
async def get_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    return documents

@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.get(Document, doc_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Count chunks for this document. Useful for the frontend to show
    # "X chunks indexed" or to know how processing is progressing.
    chunk_count_result = await db.execute(
        text("SELECT COUNT(*) FROM chunk WHERE doc_id = :doc_id"),
        {"doc_id": str(doc.id)},
    )
    chunk_count = chunk_count_result.scalar_one()

    return {
        "id": str(doc.id),
        "user_id": str(doc.user_id),
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "status": doc.status,
        "created_at": doc.created_at,
        "chunk_count": chunk_count,
    }


@router.post("/documents/upload")
@limiter.limit(UPLOAD_LIMIT, key_func=get_user_id_key)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF/DOCX allowed."
        )

    # Stream file to disk in 1MB chunks
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    total_bytes = 0
    try:
        with file_path.open("wb") as f:
            while chunk := await file.read(CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Max size is {MAX_FILE_SIZE // (1024 * 1024)} MB.",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        file_path.unlink(missing_ok=True)
        logger.error(f"Failed to save file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    if total_bytes == 0:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Save record to db
    db_record = Document(
        user_id=current_user.id,
        file_name=file.filename,
        file_type=file_extension,
        file_path=str(file_path),
    )
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)

    logger.info(f"Dispatching processing task for document {db_record.id}")
    process_document_task.delay(str(db_record.id))

    return {"id": str(db_record.id), "status": db_record.status}


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.get(Document, uuid.UUID(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Delete chunks first (foreign key constraint)
    await db.execute(
        text("DELETE FROM chunk WHERE doc_id = :doc_id"),
        {"doc_id": document_id},
    )

    file_path = Path(doc.file_path)
    if file_path.exists():
        file_path.unlink()

    await db.delete(doc)
    await db.commit()

    return {"detail": "Document deleted"}
from fastapi import (
    UploadFile,
    File,
    HTTPException,
    APIRouter,
    Depends,
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

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024


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


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file type
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF/DOCX allowed."
        )

    # Check file size
    file_content = await file.read()
    await file.seek(0)
    file_size = len(file_content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large.")

    # Save to disk
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        with file_path.open("wb") as f:
            f.write(file_content)
    except Exception as e:
        logger.error(f"Failed to save file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # Save to db
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

    # Delete file from disk
    file_path = Path(doc.file_path)
    if file_path.exists():
        file_path.unlink()

    # Delete the document record
    await db.delete(doc)
    await db.commit()

    return {"detail": "Document deleted"}
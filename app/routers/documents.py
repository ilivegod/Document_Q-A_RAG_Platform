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
import os


from app.models.document import Document
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.user import User
from app.dependencies.getUser import get_current_user
from app.workers.tasks import process_document_task
from app.dependencies.rate_limit import limiter, get_user_id_key, UPLOAD_LIMIT
from app.services.storage import (
    upload_file,
    delete_file,
    generate_presigned_url,
    make_storage_key,
)
from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB

# Local upload dir — used as temp staging area before R2 upload, and as
# the permanent storage location in dev mode (R2 not configured).
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

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
    return result.scalars().all()


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


@router.get("/documents/{document_id}/file")
async def serve_document_file(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the original document file for in-browser viewing.

    In production (R2 configured): generates a presigned URL and returns
    a 302 redirect. The browser follows it and fetches the file directly
    from R2 — no bandwidth through the API server.

    In dev mode (R2 not configured): streams the file from local disk
    as before.

    Auth-protected: a user can only fetch their own documents.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    doc = await db.get(Document, doc_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Production: presigned URL redirect
    # Production: return presigned URL as JSON so the frontend can fetch
    # the PDF directly from R2 without sending auth headers (presigned URLs
    # use query-string auth; sending Authorization header causes R2 to reject).
    if settings.r2_bucket_name:
        presigned_url = await generate_presigned_url(doc.file_path, expires_in=300)
        if presigned_url:
            return {"url": presigned_url, "type": "presigned"}

    # Dev fallback: local disk
    from fastapi.responses import FileResponse
    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File missing on server")

    media_type = (
        "application/pdf"
        if doc.file_type == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=doc.file_path,
        media_type=media_type,
        filename=doc.file_name,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/documents/upload")
@limiter.limit(UPLOAD_LIMIT, key_func=get_user_id_key)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF/DOCX allowed."
        )

    # Generate a stable document ID upfront so we can use it in the
    # storage key before the DB record exists.
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

    # Upload to R2 if configured. The storage key (or local path in dev)
    # is what we store in file_path on the DB record.
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
            # Always clean up the local temp file after R2 upload.
            temp_path.unlink(missing_ok=True)
        stored_path = storage_key
    else:
        # Dev mode: keep the local file as-is.
        stored_path = str(temp_path)

    db_record = Document(
        id=doc_id,
        user_id=current_user.id,
        file_name=file.filename,
        file_type=file_extension,
        file_path=stored_path,
    )
    db.add(db_record)
    await db.commit()

    doc_id_str = str(db_record.id)
    logger.info(f"Dispatching processing task for document {doc_id_str}")
    process_document_task.delay(doc_id_str)

    return {"id": doc_id_str, "status": db_record.status}


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

    await db.execute(
        text("DELETE FROM chunk WHERE doc_id = :doc_id"),
        {"doc_id": document_id},
    )

    # Delete from R2 or local disk.
    if settings.r2_bucket_name:
        await delete_file(doc.file_path)
    else:
        local = Path(doc.file_path)
        if local.exists():
            local.unlink()

    await db.delete(doc)
    await db.commit()

    return {"detail": "Document deleted"}
from fastapi import (
    UploadFile,
    File,
    HTTPException,
    APIRouter,
    Depends,
    BackgroundTasks,
)
from pathlib import Path
import uuid

from app.models.document import Document_Status, Document
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pipeline import process_document
from app.models.user import User
from app.dependencies.getUser import get_current_user
from app.workers.tasks import process_document_task

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSISONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024


router = APIRouter()
initial_status = Document_Status.UPLOADED


@router.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # validating file type
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSISONS:
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only PDF/DOCX allowed."
        )

    # checking file size
    file_content = await file.read()
    await file.seek(0)
    file_size = len(file_content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large.")

    # saving in memory
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        with file_path.open("wb") as f:
            f.write(file_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # saving in db

    db_record = Document(
        user_id=current_user.id,
        file_name=file.filename,
        file_type=file_extension,
        file_path=str(file_path),
        status=initial_status,
    )
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)

    print(f"Adding background task for document {db_record.id}")
    # background_tasks.add_task(process_document, db_record.id)
    process_document_task.delay(str(db_record.id))

    return {"id": str(db_record.id), "status": db_record.status}

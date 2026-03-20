from fastapi import FastAPI, UploadFile, File, HTTPException, status, APIRouter, Depends
from pathlib import Path
import uuid

from app.models.document import Document_Status, Document
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSISONS = {".pdf" , ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024

TEMP_USER_ID = uuid.UUID('11111111-1111-1111-1111-111111111111')


router = APIRouter()
initial_status  = Document_Status.UPLOADED


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), db:AsyncSession = Depends(get_db)):
    #validating file type
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSISONS:
        raise HTTPException(status_code=400, detail = "Invalid file type. Only PDF/DOCX allowed.")
    
    #checking file size
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


    #saving in db

    db_record = Document(
        user_id = TEMP_USER_ID,
        file_name = file.filename,
        file_type = file_extension,
        file_path = str(file_path),
        status = initial_status
    )
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)

    return {"id": str(db_record.id), "status": db_record.status}
    

    



    


from fastapi import FastAPI, UploadFile, File, HTTPException, status, APIRouter
from pathlib import Path
from app.main import app

ALLOWED_EXTENSISONS = {".pdf" , ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024

router = APIRouter()

@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    #validating file type
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSISONS:
        raise HTTPException(status_code=400, detail = "Invalid file type. Only PDF/DOCX allowed.")
    
    #checking file size
    file_size = await file.read()
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large.")

    # saving in memeory and db
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    



    


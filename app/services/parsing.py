

from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document

import uuid



async def parse_document(document_id:uuid.UUID, db: AsyncSession):
    doc = await db.get(Document, document_id)
    if not doc:
        return None
    file_extension = doc.file_type
    if file_extension == "pdf":
        loader = PyPDFLoader(doc.file_path)
    elif file_extension == "docx":
        loader = Docx2txtLoader(doc.file_path)
    else:
        return None 

    pages = loader.load()
    
    
    return pages
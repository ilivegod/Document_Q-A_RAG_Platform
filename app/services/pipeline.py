import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document_Status, Document
from .parsing import parse_document
from .chunking import text_splitter
from .embedding import embed_chunks
from app.database import async_session

async def process_document(document_id: uuid.UUID):
    async with async_session() as db:
        try:
            doc = await db.get(Document, document_id)
            if not doc:
                return

            doc.status = Document_Status.PROCESSING
            await db.commit()

            parsed_doc = await parse_document(document_id, db)
            if not parsed_doc:
                return
            
            splitted_text = text_splitter(1000, 400, document_id, parsed_doc)
            chunks_with_embeddings = embed_chunks(splitted_text)

            db.add_all(chunks_with_embeddings)
            await db.commit()
            doc.status = Document_Status.READY
            await db.commit()
        except Exception:
            if doc:
                doc.status = Document_Status.FAILED
                await db.commit()








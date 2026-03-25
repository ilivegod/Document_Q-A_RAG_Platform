import uuid


from app.models.document import Document_Status, Document
from .parsing import parse_document
from .chunking import text_splitter
from .embedding import embed_chunks
from app.database import async_session

import logging

logger = logging.getLogger(__name__)


async def process_document(document_id: uuid.UUID):
    async with async_session() as db:
        try:
            doc = await db.get(Document, document_id)
            if not doc:
                logger.error(f"Document {document_id} not found")
                return

            doc.status = Document_Status.PROCESSING
            await db.commit()
            logger.info("Status set to PROCESSING")

            parsed_doc = await parse_document(document_id, db)
            if not parsed_doc:
                logger.error("Parsing returned None")
                return
            logger.info(f"Parsed {len(parsed_doc)} pages")

            try:
                splitted_text = text_splitter(1000, 400, document_id, parsed_doc)
                logger.info(f"Created {len(splitted_text)} chunks")
            except Exception as e:
                logger.error(f"Chunking failed: {e}", exc_info=True)

            if not splitted_text:
                logger.error(f"splitter error")
            chunks_with_embeddings = embed_chunks(splitted_text)

            db.add_all(chunks_with_embeddings)
            await db.commit()
            doc.status = Document_Status.READY
            await db.commit()
        except Exception:
            if doc:
                doc.status = Document_Status.FAILED
                await db.commit()

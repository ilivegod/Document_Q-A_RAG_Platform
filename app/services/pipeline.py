import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.document import Document_Status, Document
from .parsing import parse_document
from .chunking import text_splitter
from .embedding import embed_chunks
from app.config import settings
import logging

logger = logging.getLogger(__name__)


async def process_document(document_id: str):
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    async with session_factory() as db:
        try:
            doc = await db.get(Document, uuid.UUID(document_id))
            if not doc:
                logger.error(f"Document {document_id} not found")
                return

            doc.status = Document_Status.PROCESSING
            await db.commit()
            logger.info("Status set to PROCESSING")

            parsed_doc = await parse_document(document_id, db)
            if not parsed_doc:
                logger.error("Parsing returned None")
                doc.status = Document_Status.FAILED
                await db.commit()
                return
            logger.info(f"Parsed {len(parsed_doc)} pages")

            splitted_text = text_splitter(1000, 400, uuid.UUID(document_id), parsed_doc)
            logger.info(f"Created {len(splitted_text)} chunks")

            chunks_with_embeddings = embed_chunks(splitted_text)
            logger.info("Embeddings generated")

            db.add_all(chunks_with_embeddings)
            await db.commit()

            doc.status = Document_Status.READY
            await db.commit()
            logger.info("Status set to READY")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            try:
                doc = await db.get(Document, uuid.UUID(document_id))
                if doc:
                    doc.status = Document_Status.FAILED
                    await db.commit()
            except Exception:
                pass

    await engine.dispose()

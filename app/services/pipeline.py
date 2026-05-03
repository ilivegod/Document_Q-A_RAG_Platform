import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.document import Document_Status, Document
from .parsing import parse_document
from .chunking import text_splitter
from .embedding import embed_chunks
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class PermanentProcessingError(Exception):
    """Raised when document processing fails in a way that won't be fixed by retrying.
    Examples: corrupt file, unsupported format, document deleted from DB."""
    pass


async def _mark_failed(document_id: str) -> None:
    """Update document status to FAILED using a fresh session.
    Used in error paths where the original session may be in a broken state."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)
    try:
        async with session_factory() as db:
            doc = await db.get(Document, uuid.UUID(document_id))
            if doc:
                doc.status = Document_Status.FAILED
                await db.commit()
                logger.info(f"Document {document_id} marked as FAILED")
            else:
                logger.warning(
                    f"Could not mark {document_id} as FAILED: document not found"
                )
    except Exception as e:
        logger.error(
            f"Failed to mark document {document_id} as FAILED: {e}",
            exc_info=True,
        )
    finally:
        await engine.dispose()


async def process_document(document_id: str) -> None:
    """End-to-end document processing pipeline.

    Raises PermanentProcessingError on unrecoverable failures (already marked FAILED).
    Re-raises other exceptions so Celery can retry the task."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    try:
        async with session_factory() as db:
            doc = await db.get(Document, uuid.UUID(document_id))
            if not doc:
                logger.error(f"Document {document_id} not found")
                raise PermanentProcessingError(f"Document {document_id} not found")

            doc.status = Document_Status.PROCESSING
            await db.commit()
            logger.info(f"Document {document_id}: status set to PROCESSING")

            # Parsing errors are permanent (corrupt file, unsupported format)
            try:
                parsed_doc = await parse_document(uuid.UUID(document_id), db)
            except Exception as e:
                logger.error(
                    f"Document {document_id}: parsing failed: {e}",
                    exc_info=True,
                )
                raise PermanentProcessingError(
                    f"Could not parse document: {e}"
                ) from e

            if not parsed_doc:
                logger.error(f"Document {document_id}: parser returned None")
                raise PermanentProcessingError("Parser returned no content")

            logger.info(f"Document {document_id}: parsed {len(parsed_doc)} pages")

            # Chunking and embedding — transient failures here will be retried
            chunks = text_splitter(1000, 400, uuid.UUID(document_id), parsed_doc)
            logger.info(f"Document {document_id}: created {len(chunks)} chunks")

            chunks_with_embeddings = embed_chunks(chunks)
            logger.info(f"Document {document_id}: embeddings generated")

            db.add_all(chunks_with_embeddings)
            await db.commit()

            doc.status = Document_Status.READY
            await db.commit()
            logger.info(f"Document {document_id}: status set to READY")

    except PermanentProcessingError:
        # Permanent failure — mark FAILED and don't re-raise.
        # Celery will see the task as successful (we handled it) and won't retry.
        await _mark_failed(document_id)
    except Exception:
        # Transient failure — re-raise so Celery retries the task.
        # Don't mark FAILED yet; we want to give it more attempts.
        logger.error(
            f"Document {document_id}: transient failure, will retry",
            exc_info=True,
        )
        raise
    finally:
        await engine.dispose()
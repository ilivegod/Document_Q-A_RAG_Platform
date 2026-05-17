import os
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.document import Document_Status, Document
from .parsing import parse_document_from_path
from .chunking import text_splitter
from .embedding import embed_chunks
from app.config import settings
from app.services.storage import download_to_tempfile
import logging

logger = logging.getLogger(__name__)


class PermanentProcessingError(Exception):
    """Raised when document processing fails in a way that won't be fixed by retrying.
    Examples: corrupt file, unsupported format, document deleted from DB."""
    pass


async def _mark_failed(document_id: str) -> None:
    """Update document status to FAILED using a fresh session."""
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

    Flow:
    1. Fetch document record from DB.
    2. Download file from R2 (or use local path in dev) to a temp file.
    3. Parse → chunk → embed → save chunks → mark READY.
    4. Clean up the temp file.

    Raises PermanentProcessingError on unrecoverable failures.
    Re-raises other exceptions so Celery can retry the task.
    """
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)
    temp_path: str | None = None

    try:
        async with session_factory() as db:
            doc = await db.get(Document, uuid.UUID(document_id))
            if not doc:
                logger.error(f"Document {document_id} not found")
                raise PermanentProcessingError(f"Document {document_id} not found")

            file_path = doc.file_path
            file_type = doc.file_type

            doc.status = Document_Status.PROCESSING
            await db.commit()
            logger.info(f"Document {document_id}: status set to PROCESSING")

            # Download from R2 to a temp local file for parsing.
            # In dev mode (R2 not configured), download_to_tempfile returns
            # the local path unchanged and no temp file is created.
            try:
                temp_path = await download_to_tempfile(file_path, suffix=file_type)
            except Exception as e:
                logger.error(
                    f"Document {document_id}: failed to download from storage: {e}",
                    exc_info=True,
                )
                raise PermanentProcessingError(
                    f"Could not retrieve file from storage: {e}"
                ) from e

            # Parsing errors are permanent (corrupt file, unsupported format)
            try:
                parsed_doc = parse_document_from_path(temp_path, file_type)
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

            chunks = text_splitter(1000, 400, uuid.UUID(document_id), parsed_doc)
            enriched = sum(1 for c in chunks if c.bboxes is not None)
            logger.info(
                f"Document {document_id}: created {len(chunks)} chunks "
                f"({enriched} with bboxes)"
            )

            chunks_with_embeddings = embed_chunks(chunks)
            logger.info(f"Document {document_id}: embeddings generated")

            db.add_all(chunks_with_embeddings)
            await db.commit()

            doc.status = Document_Status.READY
            await db.commit()
            logger.info(f"Document {document_id}: status set to READY")

    except PermanentProcessingError:
        await _mark_failed(document_id)
    except Exception:
        logger.error(
            f"Document {document_id}: transient failure, will retry",
            exc_info=True,
        )
        raise
    finally:
        # Clean up the temp file if one was created by download_to_tempfile.
        # In dev mode temp_path is the original local path — don't delete it.
        if temp_path and settings.r2_bucket_name:
            try:
                os.unlink(temp_path)
            except OSError:
                logger.warning("Could not delete temp file: %s", temp_path)
        await engine.dispose()
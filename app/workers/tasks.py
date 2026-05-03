import asyncio
import logging
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # seconds — first retry after 60s
    autoretry_for=(Exception,),
    retry_backoff=True,       # exponential backoff: 60s, 120s, 240s
    retry_backoff_max=600,    # cap individual backoff at 10 minutes
    retry_jitter=True,        # randomize backoff to avoid thundering herd
)
def process_document_task(self, document_id):
    """Celery task wrapping the async document processing pipeline.

    Retries automatically (up to 3 times with exponential backoff) on any
    exception bubbling up from process_document. PermanentProcessingError
    is handled inside process_document and won't reach here.
    """
    from app.services.pipeline import process_document

    try:
        asyncio.run(process_document(str(document_id)))
    except Exception as exc:
        # Log this attempt's failure
        attempt = self.request.retries + 1
        logger.warning(
            f"Document {document_id}: processing attempt {attempt} failed: {exc}"
        )

        # If this was the last allowed retry, mark the doc as FAILED
        # before letting Celery raise.
        if self.request.retries >= self.max_retries:
            logger.error(
                f"Document {document_id}: exhausted {self.max_retries} retries, "
                f"marking as FAILED"
            )
            from app.services.pipeline import _mark_failed
            asyncio.run(_mark_failed(str(document_id)))

        # Re-raise so Celery's autoretry_for kicks in (or final failure if exhausted)
        raise
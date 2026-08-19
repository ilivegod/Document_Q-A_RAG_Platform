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


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def auto_analyze_project_task(self, document_id: str, project_id: str, user_id: str):
    """Run requirements extraction and technology suggestions after document READY."""
    from app.services.auto_analyzer import auto_analyze_project

    try:
        asyncio.run(auto_analyze_project(document_id, project_id, user_id))
    except Exception as exc:
        attempt = self.request.retries + 1
        logger.warning(
            "Project analysis for document %s attempt %d failed: %s",
            document_id,
            attempt,
            exc,
        )
        raise


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_sow_task(self, sow_document_id: str, user_id: str, project_id: str):
    """Generate SOW tiers and labor estimates for a sow_documents row."""
    from app.services.sow_generator import mark_sow_generation_failed, run_sow_generation

    try:
        asyncio.run(run_sow_generation(sow_document_id, user_id, project_id))
    except Exception as exc:
        attempt = self.request.retries + 1
        logger.warning(
            "SOW %s generation attempt %d failed: %s",
            sow_document_id,
            attempt,
            exc,
        )
        if self.request.retries >= self.max_retries:
            logger.error(
                "SOW %s: exhausted %d retries, marking generation FAILED",
                sow_document_id,
                self.max_retries,
            )
            asyncio.run(mark_sow_generation_failed(sow_document_id))
        raise


@celery_app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def discover_prospects_task(self, search_id: str):
    """Discover local businesses and score them as prospects."""
    from app.services.prospect_service import mark_prospect_search_failed, run_prospect_discovery

    try:
        asyncio.run(run_prospect_discovery(search_id))
    except Exception as exc:
        logger.warning("Prospect search %s attempt failed: %s", search_id, exc)
        if self.request.retries >= self.max_retries:
            asyncio.run(mark_prospect_search_failed(search_id, str(exc)))
        raise
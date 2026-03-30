import asyncio
from app.workers.celery_app import celery_app


@celery_app.task
def process_document_task(document_id):
    from app.services.pipeline import process_document

    asyncio.run(process_document(str(document_id)))

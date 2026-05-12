from celery import Celery

from app.sentry import init_sentry
init_sentry()

from app.config import settings



celery_app = Celery(
    "docqa",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.autodiscover_tasks(["app.workers"])

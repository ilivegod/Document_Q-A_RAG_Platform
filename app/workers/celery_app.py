from celery import Celery
from celery.signals import worker_process_init

from app.sentry import init_sentry
init_sentry()

from app.config import settings



celery_app = Celery(
    "docqa",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.autodiscover_tasks(["app.workers"])


@worker_process_init.connect
def _dispose_db_engine_after_fork(**_kwargs) -> None:
    """Drop inherited asyncpg pool connections after Celery prefork."""
    import asyncio

    try:
        from app.database import engine

        asyncio.run(engine.dispose())
    except Exception:
        pass

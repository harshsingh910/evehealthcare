"""
Celery application configuration.

Uses Redis as both broker and result backend.
Separate Redis DB (db=1) isolates task queue from the cache (db=0).
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "eve_healthcare",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Bounded retries with exponential backoff
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Auto-discover tasks in the tasks package
celery_app.autodiscover_tasks(["app.tasks"])

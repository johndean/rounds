"""
Celery app bootstrap. Worker scripts/start.sh runs:
    celery -A app.tasks.celery_app.celery_app worker --concurrency=2 --queues=celery

Real task implementations (ingest, transcribe, slide_extract, frame_task,
align, fuse, iil, ai_mode, classify_discrepancies, burn_captions) land in
Phase 6 / U37-U45 per docs/plans/2026-05-17-001-feat-rounds-bootstrap-plan.md.
For now the worker boots clean with no registered tasks so the Railway
deploy can succeed, queues are reachable for future tasks, and the broker
connection is exercised.
"""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "rounds",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.ingest",
        "app.tasks.transcribe",
        "app.tasks.slide_extract",
        "app.tasks.align",
        "app.tasks.finalize",
    ],
)

# Retry posture (LOCKED — audit §6)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=settings.CELERY_RETRY_BACKOFF_BASE,
    task_max_retries=settings.CELERY_MAX_RETRIES,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,  # avoid greedy reservation for long jobs
    task_default_queue="celery",
)

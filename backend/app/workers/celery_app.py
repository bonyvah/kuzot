from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

celery_app = Celery(
    "kuzot",
    broker=settings.RABBITMQ_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.scraping",
        "app.workers.tasks.browser",
        "app.workers.tasks.embedding",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_queues=(
        Queue("scraping", Exchange("scraping"), routing_key="scraping"),
        Queue("browser", Exchange("browser"), routing_key="browser"),
        Queue("embedding", Exchange("embedding"), routing_key="embedding"),
    ),
    task_routes={
        "app.workers.tasks.scraping.*": {"queue": "scraping"},
        "app.workers.tasks.browser.*": {"queue": "browser"},
        "app.workers.tasks.embedding.*": {"queue": "embedding"},
    },
    beat_schedule={
        "dispatch-due-scrapes": {
            "task": "app.workers.tasks.scraping.dispatch_due_scrapes",
            "schedule": 60.0,
        },
    },
)
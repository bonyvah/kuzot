from celery import Celery
from celery.signals import worker_init, worker_process_init
from kombu import Exchange, Queue

from app.core.config import settings
from app.core.tracing import setup_tracing

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
        "requeue-stale-embeddings": {
            "task": "app.workers.tasks.embedding.requeue_stale_events",
            "schedule": 300.0,
        },
    },
)


# The exporter's thread doesn't survive a fork, so prefork workers start tracing
# in each child; pools that never fork (gevent) don't fire worker_process_init.
@worker_process_init.connect(weak=False)
def _trace_forked_worker(**_) -> None:
    setup_tracing("kuzot-worker")


@worker_init.connect(weak=False)
def _trace_unforked_worker(sender, **_) -> None:
    if "prefork" not in str(sender.pool_cls):
        setup_tracing("kuzot-worker")

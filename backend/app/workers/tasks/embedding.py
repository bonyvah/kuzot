import openai
from pinecone import errors as pinecone_errors

from app.workers.celery_app import celery_app
from app.workers.embedding_pipeline import (
    URLBusy,
    claim_stale_events,
    mark_failed,
    run_embedding,
)

BUSY_RETRY_SECONDS = 15

TRANSIENT = (
    openai.APIConnectionError,  # includes APITimeoutError
    openai.RateLimitError,
    openai.InternalServerError,
    pinecone_errors.PineconeConnectionError,
    pinecone_errors.PineconeTimeoutError,
    pinecone_errors.RateLimitError,
    pinecone_errors.ServiceError,
)


@celery_app.task(
    bind=True,
    name="app.workers.tasks.embedding.process_change_event",
    max_retries=5,
)
def process_change_event(self, event_id: str) -> dict:
    try:
        return run_embedding(event_id)
    except URLBusy as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=BUSY_RETRY_SECONDS)
        # not a failure: the event stays pending and the sweeper re-queues it
        return {"status": "busy"}
    except TRANSIENT as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * 2**self.request.retries)
        mark_failed(event_id, f"{type(exc).__name__}: {exc}")
        raise
    except Exception as exc:
        mark_failed(event_id, f"{type(exc).__name__}: {exc}")
        raise


@celery_app.task(name="app.workers.tasks.embedding.requeue_stale_events")
def requeue_stale_events() -> int:
    event_ids = claim_stale_events()
    for event_id in event_ids:
        process_change_event.apply_async(args=[event_id], ignore_result=True)
    return len(event_ids)

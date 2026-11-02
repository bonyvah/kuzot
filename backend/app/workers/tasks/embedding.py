import openai
from pinecone import errors as pinecone_errors

from app.workers.celery_app import celery_app
from app.insights.headline import EmptyHeadline
from app.workers.embedding_pipeline import (
    URLBusy,
    claim_stale_events,
    mark_failed,
    run_embedding,
)
from app.workers.insights import mark_headline_failed, write_headline

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
        result = run_embedding(event_id)
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
    if result.get("insight_id"):
        write_insight_headline.apply_async(args=[result["insight_id"]], ignore_result=True)
    return result


@celery_app.task(
    bind=True,
    name="app.workers.tasks.embedding.write_insight_headline",
    max_retries=4,
)
def write_insight_headline(self, insight_id: str) -> str | None:
    """Replace an insight's fallback headline with an AI one; keep the fallback on failure."""
    try:
        return write_headline(insight_id)
    except (*TRANSIENT, EmptyHeadline) as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * 2**self.request.retries)
        mark_headline_failed(insight_id)
        return None
    except Exception:
        mark_headline_failed(insight_id)
        raise


@celery_app.task(name="app.workers.tasks.embedding.requeue_stale_events")
def requeue_stale_events() -> int:
    event_ids = claim_stale_events()
    for event_id in event_ids:
        process_change_event.apply_async(args=[event_id], ignore_result=True)
    return len(event_ids)

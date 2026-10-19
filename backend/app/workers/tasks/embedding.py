import openai
from pinecone import errors as pinecone_errors

from app.workers.celery_app import celery_app
from app.workers.embedding_pipeline import mark_failed, run_embedding

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
    except TRANSIENT as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * 2**self.request.retries)
        mark_failed(event_id, f"{type(exc).__name__}: {exc}")
        raise
    except Exception as exc:
        mark_failed(event_id, f"{type(exc).__name__}: {exc}")
        raise

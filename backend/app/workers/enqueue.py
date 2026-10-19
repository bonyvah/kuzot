from uuid import UUID

from app.workers.celery_app import celery_app


def enqueue_scrape(job_id: UUID) -> None:
    """Hand a PENDING ScrapeJob to the scraping queue (routed by task name)."""
    # job state lives in Postgres, so skip the Redis result backend on publish
    celery_app.send_task(
        "app.workers.tasks.scraping.scrape_url",
        args=[str(job_id)],
        ignore_result=True,
    )

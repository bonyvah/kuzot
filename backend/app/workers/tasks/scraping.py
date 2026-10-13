from datetime import timedelta

from sqlalchemy import exists, literal_column, or_, select

from app.models import MonitoredURL, ScrapeJob, ScrapeJobStatus, TriggeredBy
from app.workers.celery_app import celery_app
from app.workers.db import SyncSession
from app.workers.pipeline import BrowserRequired, run_scrape, utcnow


@celery_app.task(bind=True, name="app.workers.tasks.scraping.scrape_url")
def scrape_url(self, job_id: str) -> dict:
    try:
        return run_scrape(job_id, self.request.id, use_browser=False)
    except BrowserRequired:
        celery_app.send_task(
            "app.workers.tasks.browser.scrape_url_browser", args=[job_id]
        )
        return {"status": "escalated_to_browser"}


@celery_app.task(name="app.workers.tasks.scraping.dispatch_due_scrapes")
def dispatch_due_scrapes() -> int:
    now = utcnow()
    one_minute = literal_column("interval '1 minute'")
    has_active_job = exists().where(
        ScrapeJob.monitored_url_id == MonitoredURL.id,
        ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING]),
        ScrapeJob.created_at > now - timedelta(minutes=30),
    )
    due_query = select(MonitoredURL.id).where(
        MonitoredURL.is_active.is_(True),
        MonitoredURL.scrape_interval_minutes.is_not(None),
        or_(
            MonitoredURL.last_scraped_at.is_(None),
            MonitoredURL.last_scraped_at
            + MonitoredURL.scrape_interval_minutes * one_minute
            <= now + timedelta(seconds=30),  # slack: scrapes finish after the tick
        ),
        ~has_active_job,
    )

    with SyncSession() as db:
        due_ids = db.scalars(due_query).all()
        jobs = [
            ScrapeJob(monitored_url_id=url_id, triggered_by=TriggeredBy.SCHEDULER)
            for url_id in due_ids
        ]
        db.add_all(jobs)
        db.commit()
        job_ids = [str(job.id) for job in jobs]

    for job_id in job_ids:
        scrape_url.delay(job_id)
    return len(job_ids)
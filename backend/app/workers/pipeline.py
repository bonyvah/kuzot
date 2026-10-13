from datetime import datetime, timezone
from uuid import UUID

from app.models import MonitoredURL, ScrapeJob, ScrapeJobStatus
from app.scraping.browser import fetch_rendered
from app.scraping.extractor import extract_text, is_thin, normalize_text
from app.scraping.fetcher import FetchError, TransientFetchError, fetch_html
from app.scraping.hashing import content_hash, has_changed
from app.workers.celery_app import celery_app
from app.workers.db import SyncSession, get_mongo_db


class BrowserRequired(Exception):
    """httpx wasn't enough for this page: retry it with the headless browser."""


def utcnow() -> datetime:
    # our columns are TIMESTAMP WITHOUT TIME ZONE, so store naive UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fail(job_id: UUID, message: str) -> None:
    with SyncSession() as db:
        job = db.get(ScrapeJob, job_id)
        if job is None:
            return
        job.status = ScrapeJobStatus.FAILED
        job.finished_at = utcnow()
        job.error_message = message[:1000]
        db.commit()


def run_scrape(job_id: str, task_id: str | None, *, use_browser: bool) -> dict:
    job_uuid = UUID(job_id)

    # 1. short DB session: mark running, read what we need, close it
    with SyncSession() as db:
        job = db.get(ScrapeJob, job_uuid)
        if job is None:
            raise ValueError(f"ScrapeJob {job_id} not found")
        job.status = ScrapeJobStatus.RUNNING
        job.started_at = utcnow()
        job.celery_task_id = task_id
        url_row = db.get(MonitoredURL, job.monitored_url_id)
        if url_row is None:
            raise ValueError(f"MonitoredURL {job.monitored_url_id} not found")
        url = url_row.url
        url_id = url_row.id
        previous_hash = url_row.last_content_hash
        db.commit()

    # 2. network + CPU work, no DB connection held
    fetch = fetch_rendered if use_browser else fetch_html
    try:
        result = fetch(url)
        raw_text = extract_text(result.content)
        if raw_text is None or is_thin(raw_text):
            if not use_browser:
                raise BrowserRequired()
            raise FetchError("Too little text extracted even after browser rendering")
        text = normalize_text(raw_text)
        new_hash = content_hash(text)
    except BrowserRequired:
        raise
    except (FetchError, TransientFetchError) as exc:
        # 403 is often an anti-bot block that a real browser gets past
        if not use_browser and getattr(exc, "status_code", None) == 403:
            raise BrowserRequired() from exc
        _fail(job_uuid, str(exc))
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        _fail(job_uuid, f"Unexpected: {type(exc).__name__}: {exc}")
        raise

    # 3. compare, store in Mongo only when content changed
    changed = has_changed(previous_hash, new_hash)
    snapshot_id = None
    event_id = None
    now = utcnow()
    if changed:
        mongo_db = get_mongo_db()
        snapshot_id = mongo_db.page_snapshots.insert_one(
            {
                "monitored_url_id": str(url_id),
                "url": result.url,
                "content_hash": new_hash,
                "text": text,
                "scraped_at": now,
                "rendered_with": "browser" if use_browser else "httpx",
            }
        ).inserted_id
        event_id = mongo_db.change_events.insert_one(
            {
                "monitored_url_id": str(url_id),
                "snapshot_id": snapshot_id,
                "previous_hash": previous_hash,
                "new_hash": new_hash,
                "detected_at": now,
                "embedding_status": "pending",
            }
        ).inserted_id

    # 4. short DB session: record the outcome
    with SyncSession() as db:
        job = db.get(ScrapeJob, job_uuid)
        if job is None:
            raise ValueError(f"ScrapeJob {job_id} not found")
        job.status = ScrapeJobStatus.SUCCESS
        job.finished_at = utcnow()
        job.content_changed = changed
        job.mongo_snapshot_id = str(snapshot_id) if snapshot_id else None
        url_row = db.get(MonitoredURL, url_id)
        if url_row is None:
            raise ValueError(f"MonitoredURL {url_id} not found")
        url_row.last_scraped_at = now
        if changed:
            url_row.last_content_hash = new_hash
        db.commit()

    if event_id:
        celery_app.send_task(
            "app.workers.tasks.embedding.process_change_event",
            args=[str(event_id)],
        )
    return {"status": "success", "changed": changed, "browser": use_browser}

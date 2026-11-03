from datetime import datetime, timezone
from uuid import UUID

from redis.exceptions import RedisError

from app.models import MonitoredURL, ScrapeJob, ScrapeJobStatus
from app.scraping.fetcher import FetchError, TransientFetchError
from app.scraping.hashing import content_hash, has_changed
from app.scraping.robots import (
    RobotsUnreachable,
    fetch_robots_txt,
    is_allowed,
    robots_url,
)
from app.sources import BrowserRequired, SourceResult, source_for
from app.workers.celery_app import celery_app
from app.workers.db import SyncSession, get_mongo_db, get_redis

ROBOTS_TTL_SECONDS = 24 * 60 * 60  # how long a site's robots.txt is trusted
ROBOTS_BLOCKED = "Blocked by the site's robots.txt, so it was not scraped"


__all__ = ["BrowserRequired", "robots_allows", "run_scrape", "utcnow"]


def utcnow() -> datetime:
    # our columns are TIMESTAMP WITHOUT TIME ZONE, so store naive UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)


def robots_allows(url: str) -> bool:
    """Check robots.txt, cached in Redis per site. Raises RobotsUnreachable."""
    key = f"robots:{robots_url(url)}"
    redis = get_redis()
    try:
        cached = redis.get(key)
    except RedisError:
        cached = None  # the cache is an optimization: fetch it instead
    if cached is not None:
        return is_allowed(cached.decode("utf-8"), url)

    # unreachable isn't cached, so the next scheduled run asks again
    robots_txt = fetch_robots_txt(url)
    try:
        redis.setex(key, ROBOTS_TTL_SECONDS, robots_txt)
    except RedisError:
        pass
    return is_allowed(robots_txt, url)


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
        url_type = url_row.url_type
        url_id = url_row.id
        previous_hash = url_row.last_content_hash
        db.commit()

    # 2. network + CPU work, no DB connection held
    source = source_for(url_type, use_browser=use_browser)
    if source.respects_robots:
        try:
            allowed = robots_allows(url)
        except RobotsUnreachable as exc:
            message = f"Couldn't read robots.txt ({exc}), so it was not scraped"
            _fail(job_uuid, message)
            return {"status": "failed", "error": message}
        if not allowed:
            _fail(job_uuid, ROBOTS_BLOCKED)
            return {"status": "blocked"}

    try:
        result = source.read(url)
    except BrowserRequired:
        raise
    except (FetchError, TransientFetchError) as exc:
        _fail(job_uuid, str(exc))
        return {"status": "failed", "error": str(exc)}
    except Exception as exc:
        _fail(job_uuid, f"Unexpected: {type(exc).__name__}: {exc}")
        raise

    return _record(job_uuid, url_id, previous_hash, result) | {"browser": use_browser}


def _record(job_uuid: UUID, url_id: UUID, previous_hash: str | None, result: SourceResult) -> dict:
    # 3. compare, store in Mongo only when content changed
    new_hash = content_hash(result.text)
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
                "text": result.text,
                "paragraphs": result.paragraphs,  # line structure, for chunking
                "scraped_at": now,
                "rendered_with": result.via,
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
            raise ValueError(f"ScrapeJob {job_uuid} not found")
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
            ignore_result=True,
        )
    return {"status": "success", "changed": changed}

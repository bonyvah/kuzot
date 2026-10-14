import uuid
from datetime import timedelta

import pytest
from bson import ObjectId
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import (
    Competitor,
    MonitoredURL,
    Organization,
    ScrapeJob,
    ScrapeJobStatus,
    TriggeredBy,
    URLType,
    Workspace,
)
from app.scraping.fetcher import FetchError, FetchResult, TransientFetchError
from app.workers import pipeline
from app.workers.pipeline import BrowserRequired, run_scrape, utcnow
from app.workers.tasks import scraping
from app.workers.tasks.browser import scrape_url_browser
from app.workers.tasks.scraping import dispatch_due_scrapes, scrape_url

LONG_TEXT = (
    "Pricing page. The Pro plan costs $20 per month and includes all features. "
) * 6


def page(text: str = LONG_TEXT) -> bytes:
    return f"<html><body><article><p>{text}</p></article></body></html>".encode()


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        doc = {**doc, "_id": ObjectId()}
        self.docs.append(doc)
        return FakeInsertResult(doc["_id"])


class FakeMongo:
    def __init__(self):
        self.page_snapshots = FakeCollection()
        self.change_events = FakeCollection()


@pytest.fixture
def sync_session(monkeypatch):
    engine = create_engine(
        settings.DATABASE_URL_TEST.replace("+asyncpg", "+psycopg"), poolclass=NullPool
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "SyncSession", factory)
    monkeypatch.setattr(scraping, "SyncSession", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def mongo(monkeypatch):
    fake = FakeMongo()
    monkeypatch.setattr(pipeline, "get_mongo_db", lambda: fake)
    return fake


@pytest.fixture
def sent_tasks(monkeypatch):
    sent = []
    monkeypatch.setattr(
        pipeline.celery_app,
        "send_task",
        lambda name, args=None, **kw: sent.append((name, args)),
    )
    monkeypatch.setattr(
        scraping.celery_app,
        "send_task",
        lambda name, args=None, **kw: sent.append((name, args)),
    )
    return sent


@pytest.fixture
def make_url(sync_session):
    def _make(**overrides) -> uuid.UUID:
        suffix = uuid.uuid4().hex[:10]
        with sync_session() as db:
            org = Organization(name="o", slug=f"org-{suffix}")
            db.add(org)
            db.flush()
            ws = Workspace(org_id=org.id, name="w")
            db.add(ws)
            db.flush()
            comp = Competitor(workspace_id=ws.id, name="c")
            db.add(comp)
            db.flush()
            fields = dict(
                competitor_id=comp.id,
                url=f"https://example.com/{suffix}",
                url_type=URLType.PRICING,
                scrape_interval_minutes=60,
                is_active=True,
            )
            fields.update(overrides)
            url = MonitoredURL(**fields)
            db.add(url)
            db.commit()
            return url.id

    return _make


@pytest.fixture
def make_job(sync_session):
    def _make(url_id, status=ScrapeJobStatus.PENDING, **kw) -> str:
        with sync_session() as db:
            job = ScrapeJob(
                monitored_url_id=url_id,
                triggered_by=TriggeredBy.MANUAL,
                status=status,
                **kw,
            )
            db.add(job)
            db.commit()
            return str(job.id)

    return _make


def fetch_returning(content: bytes, status: int = 200):
    return lambda url: FetchResult(url=url, status_code=status, content=content)


def fetch_raising(exc: Exception):
    def _fetch(url):
        raise exc

    return _fetch


def get_job(sync_session, job_id) -> ScrapeJob:
    with sync_session() as db:
        return db.get(ScrapeJob, uuid.UUID(job_id))


def get_url(sync_session, url_id) -> MonitoredURL:
    with sync_session() as db:
        return db.get(MonitoredURL, url_id)


# ── run_scrape ────────────────────────────────────────────────────


def test_first_scrape_stores_snapshot_and_event(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(page()))
    url_id = make_url()
    job_id = make_job(url_id)

    result = run_scrape(job_id, "task-1", use_browser=False)

    assert result == {"status": "success", "changed": True, "browser": False}
    job = get_job(sync_session, job_id)
    assert job.status == ScrapeJobStatus.SUCCESS
    assert job.content_changed is True
    assert job.celery_task_id == "task-1"
    assert job.started_at and job.finished_at
    assert job.mongo_snapshot_id == str(mongo.page_snapshots.docs[0]["_id"])

    url = get_url(sync_session, url_id)
    snapshot = mongo.page_snapshots.docs[0]
    assert url.last_content_hash == snapshot["content_hash"]
    assert url.last_scraped_at is not None
    assert snapshot["rendered_with"] == "httpx"
    assert snapshot["monitored_url_id"] == str(url_id)

    event = mongo.change_events.docs[0]
    assert event["embedding_status"] == "pending"
    assert event["previous_hash"] is None
    assert event["new_hash"] == snapshot["content_hash"]
    assert sent_tasks == [
        ("app.workers.tasks.embedding.process_change_event", [str(event["_id"])])
    ]


def test_unchanged_content_stores_nothing_and_triggers_nothing(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(page()))
    url_id = make_url()
    run_scrape(make_job(url_id), None, use_browser=False)
    sent_tasks.clear()

    job_id = make_job(url_id)
    result = run_scrape(job_id, None, use_browser=False)

    assert result["changed"] is False
    job = get_job(sync_session, job_id)
    assert job.status == ScrapeJobStatus.SUCCESS
    assert job.content_changed is False
    assert job.mongo_snapshot_id is None
    assert len(mongo.page_snapshots.docs) == 1
    assert len(mongo.change_events.docs) == 1
    assert sent_tasks == []


def test_whitespace_only_difference_is_not_a_change(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    url_id = make_url()
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(page()))
    run_scrape(make_job(url_id), None, use_browser=False)

    reflowed = page(LONG_TEXT.replace(". ", ".\n    "))
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(reflowed))
    result = run_scrape(make_job(url_id), None, use_browser=False)

    assert result["changed"] is False
    assert len(mongo.page_snapshots.docs) == 1


def test_content_change_creates_second_event_with_previous_hash(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    url_id = make_url()
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(page()))
    run_scrape(make_job(url_id), None, use_browser=False)
    first_hash = mongo.page_snapshots.docs[0]["content_hash"]

    monkeypatch.setattr(
        pipeline, "fetch_html", fetch_returning(page(LONG_TEXT.replace("$20", "$25")))
    )
    result = run_scrape(make_job(url_id), None, use_browser=False)

    assert result["changed"] is True
    assert len(mongo.change_events.docs) == 2
    assert mongo.change_events.docs[1]["previous_hash"] == first_hash
    assert get_url(sync_session, url_id).last_content_hash != first_hash


def test_thin_page_on_httpx_requests_browser(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    shell = b"<html><body><div id='root'></div></body></html>"
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(shell))
    job_id = make_job(make_url())

    with pytest.raises(BrowserRequired):
        run_scrape(job_id, None, use_browser=False)

    assert get_job(sync_session, job_id).status == ScrapeJobStatus.RUNNING
    assert mongo.page_snapshots.docs == []


def test_403_on_httpx_requests_browser(
    monkeypatch, sync_session, mongo, make_url, make_job
):
    monkeypatch.setattr(
        pipeline, "fetch_html", fetch_raising(FetchError("HTTP 403", status_code=403))
    )
    with pytest.raises(BrowserRequired):
        run_scrape(make_job(make_url()), None, use_browser=False)


def test_404_fails_job_without_browser(
    monkeypatch, sync_session, mongo, make_url, make_job
):
    monkeypatch.setattr(
        pipeline, "fetch_html", fetch_raising(FetchError("HTTP 404", status_code=404))
    )
    job_id = make_job(make_url())

    result = run_scrape(job_id, None, use_browser=False)

    assert result["status"] == "failed"
    job = get_job(sync_session, job_id)
    assert job.status == ScrapeJobStatus.FAILED
    assert job.error_message == "HTTP 404"
    assert job.finished_at is not None


def test_transient_error_fails_job(
    monkeypatch, sync_session, mongo, make_url, make_job
):
    monkeypatch.setattr(
        pipeline, "fetch_html", fetch_raising(TransientFetchError("HTTP 503"))
    )
    job_id = make_job(make_url())

    assert run_scrape(job_id, None, use_browser=False)["status"] == "failed"
    assert get_job(sync_session, job_id).error_message == "HTTP 503"


def test_unexpected_error_fails_job_and_reraises(
    monkeypatch, sync_session, mongo, make_url, make_job
):
    monkeypatch.setattr(pipeline, "fetch_html", fetch_raising(RuntimeError("boom")))
    job_id = make_job(make_url())

    with pytest.raises(RuntimeError):
        run_scrape(job_id, None, use_browser=False)

    job = get_job(sync_session, job_id)
    assert job.status == ScrapeJobStatus.FAILED
    assert job.error_message is not None
    assert "RuntimeError: boom" in job.error_message


def test_browser_mode_uses_rendered_fetcher_and_marks_snapshot(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    monkeypatch.setattr(
        pipeline, "fetch_html", fetch_raising(AssertionError("httpx must not run"))
    )
    monkeypatch.setattr(pipeline, "fetch_rendered", fetch_returning(page()))
    job_id = make_job(make_url())

    result = run_scrape(job_id, None, use_browser=True)

    assert result == {"status": "success", "changed": True, "browser": True}
    assert mongo.page_snapshots.docs[0]["rendered_with"] == "browser"


def test_thin_page_after_browser_fails_job(
    monkeypatch, sync_session, mongo, make_url, make_job
):
    shell = b"<html><body><div id='root'></div></body></html>"
    monkeypatch.setattr(pipeline, "fetch_rendered", fetch_returning(shell))
    job_id = make_job(make_url())

    result = run_scrape(job_id, None, use_browser=True)

    assert result["status"] == "failed"
    job = get_job(sync_session, job_id)
    assert job.status == ScrapeJobStatus.FAILED
    assert job.error_message is not None
    assert "browser rendering" in job.error_message


def test_403_in_browser_mode_fails_instead_of_looping(
    monkeypatch, sync_session, mongo, make_url, make_job
):
    monkeypatch.setattr(
        pipeline,
        "fetch_rendered",
        fetch_raising(FetchError("HTTP 403", status_code=403)),
    )
    job_id = make_job(make_url())

    assert run_scrape(job_id, None, use_browser=True)["status"] == "failed"


def test_missing_job_raises(sync_session, mongo):
    with pytest.raises(ValueError, match="not found"):
        run_scrape(str(uuid.uuid4()), None, use_browser=False)


# ── Celery task wrappers ──────────────────────────────────────────


def test_scrape_url_escalates_to_browser_queue(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    shell = b"<html><body><div id='root'></div></body></html>"
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(shell))
    job_id = make_job(make_url())

    result = scrape_url.apply(args=[job_id]).get()

    assert result == {"status": "escalated_to_browser"}
    assert sent_tasks == [("app.workers.tasks.browser.scrape_url_browser", [job_id])]


def test_scrape_url_runs_pipeline_with_httpx(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    monkeypatch.setattr(pipeline, "fetch_html", fetch_returning(page()))
    job_id = make_job(make_url())

    result = scrape_url.apply(args=[job_id]).get()

    assert result["status"] == "success"
    assert get_job(sync_session, job_id).celery_task_id is not None


def test_scrape_url_browser_task_uses_browser(
    monkeypatch, sync_session, mongo, sent_tasks, make_url, make_job
):
    monkeypatch.setattr(pipeline, "fetch_rendered", fetch_returning(page()))
    job_id = make_job(make_url())

    result = scrape_url_browser.apply(args=[job_id]).get()

    assert result["browser"] is True


def test_tasks_route_to_expected_queues():
    from app.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert routes["app.workers.tasks.scraping.*"]["queue"] == "scraping"
    assert routes["app.workers.tasks.browser.*"]["queue"] == "browser"
    assert routes["app.workers.tasks.embedding.*"]["queue"] == "embedding"


# ── dispatch_due_scrapes ──────────────────────────────────────────


@pytest.fixture
def delayed(monkeypatch):
    calls = []
    monkeypatch.setattr(scrape_url, "delay", lambda job_id: calls.append(job_id))
    return calls


def jobs_for(sync_session, url_id) -> list[ScrapeJob]:
    with sync_session() as db:
        return db.query(ScrapeJob).filter_by(monitored_url_id=url_id).all()


def test_never_scraped_url_is_dispatched(sync_session, delayed, make_url):
    url_id = make_url()

    dispatch_due_scrapes()

    jobs = jobs_for(sync_session, url_id)
    assert len(jobs) == 1
    assert jobs[0].triggered_by == TriggeredBy.SCHEDULER
    assert jobs[0].status == ScrapeJobStatus.PENDING
    assert str(jobs[0].id) in delayed


def test_overdue_url_is_dispatched(sync_session, delayed, make_url):
    url_id = make_url(last_scraped_at=utcnow() - timedelta(minutes=61))
    dispatch_due_scrapes()
    assert len(jobs_for(sync_session, url_id)) == 1


def test_recently_scraped_url_is_not_dispatched(sync_session, delayed, make_url):
    url_id = make_url(last_scraped_at=utcnow() - timedelta(minutes=10))
    dispatch_due_scrapes()
    assert jobs_for(sync_session, url_id) == []


def test_slack_catches_url_that_is_seconds_early(sync_session, delayed, make_url):
    url_id = make_url(
        scrape_interval_minutes=1,
        last_scraped_at=utcnow() - timedelta(seconds=45),
    )
    dispatch_due_scrapes()
    assert len(jobs_for(sync_session, url_id)) == 1


def test_manual_only_inactive_urls_are_skipped(sync_session, delayed, make_url):
    manual = make_url(scrape_interval_minutes=None)
    inactive = make_url(is_active=False)

    dispatch_due_scrapes()

    assert jobs_for(sync_session, manual) == []
    assert jobs_for(sync_session, inactive) == []


@pytest.mark.parametrize("status", [ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING])
def test_url_with_active_job_is_not_dispatched_again(
    sync_session, delayed, make_url, make_job, status
):
    url_id = make_url()
    make_job(url_id, status=status)

    dispatch_due_scrapes()

    assert len(jobs_for(sync_session, url_id)) == 1


def test_finished_job_does_not_block_dispatch(
    sync_session, delayed, make_url, make_job
):
    url_id = make_url()
    make_job(url_id, status=ScrapeJobStatus.FAILED)

    dispatch_due_scrapes()

    assert len(jobs_for(sync_session, url_id)) == 2


def test_dispatch_returns_count(sync_session, delayed, make_url):
    # other tests leave rows behind, so only assert our rows are included
    make_url()
    make_url()
    assert dispatch_due_scrapes() >= 2

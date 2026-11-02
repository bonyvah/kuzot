import uuid
from datetime import datetime, timedelta

import httpx2
import openai
import pytest
from bson import ObjectId
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import Competitor, MonitoredURL, Organization, URLType, Workspace
from app.workers import embedding_pipeline
from app.workers.embedding_pipeline import URLBusy, claim_stale_events, run_embedding
from app.workers.tasks import embedding as embedding_tasks
from app.workers.tasks.embedding import process_change_event, requeue_stale_events


def _matches(doc: dict, query: dict) -> bool:
    for key, cond in query.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in cond):
                return False
            continue
        value = doc.get(key)
        if isinstance(cond, dict):
            if "$in" in cond and value not in cond["$in"]:
                return False
            if "$gt" in cond and not (value is not None and value > cond["$gt"]):
                return False
            if "$lt" in cond and not (value is not None and value < cond["$lt"]):
                return False
        elif value != cond:
            return False
    return True


class FakeCollection:
    def __init__(self):
        self.docs = []

    def find(self, query=None, projection=None):
        return [d for d in self.docs if _matches(d, query or {})]

    def find_one(self, query):
        found = self.find(query)
        return found[0] if found else None

    def insert_one(self, doc):
        doc = {"_id": ObjectId(), **doc}
        self.docs.append(doc)
        return doc["_id"]

    def insert_many(self, docs, ordered=True):
        self.docs.extend(dict(d) for d in docs)

    def update_one(self, query, update):
        for d in self.find(query)[:1]:
            d.update(update["$set"])

    def update_many(self, query, update):
        for d in self.find(query):
            d.update(update["$set"])

    def replace_one(self, query, doc, upsert=False):
        self.docs = [d for d in self.docs if not _matches(d, query)]
        self.docs.append({**query, **doc})


class FakeMongo:
    def __init__(self):
        self.page_snapshots = FakeCollection()
        self.change_events = FakeCollection()
        self.page_chunks = FakeCollection()
        self.insights = FakeCollection()


class FakeVectorStore:
    """In-memory stand-in for app.embedding.vector_store, keyed by namespace."""

    def __init__(self):
        self.namespaces: dict[str, dict[str, dict]] = {}

    def upsert(self, vectors, namespace):
        ns = self.namespaces.setdefault(namespace, {})
        for v in vectors:
            ns[v["id"]] = {**v, "metadata": dict(v["metadata"])}

    def set_metadata(self, ids, metadata, namespace):
        for id_ in ids:
            self.namespaces[namespace][id_]["metadata"].update(metadata)

    def current_texts(self, namespace):
        return {
            v["metadata"]["text"]
            for v in self.namespaces.get(namespace, {}).values()
            if v["metadata"]["is_current"]
        }


class FakeLock:
    def __init__(self, held: set[str], name: str):
        self.held, self.name = held, name

    def acquire(self) -> bool:
        if self.name in self.held:
            return False
        self.held.add(self.name)
        return True

    def release(self) -> None:
        self.held.discard(self.name)


class FakeRedis:
    def __init__(self):
        self.held: set[str] = set()

    def lock(self, name, timeout=None, blocking=True):
        return FakeLock(self.held, name)


@pytest.fixture(autouse=True)
def redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(embedding_pipeline, "get_redis", lambda: fake)
    return fake


@pytest.fixture
def sync_session(monkeypatch):
    engine = create_engine(
        settings.DATABASE_URL_TEST.replace("+asyncpg", "+psycopg"), poolclass=NullPool
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(embedding_pipeline, "SyncSession", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def mongo(monkeypatch):
    fake = FakeMongo()
    monkeypatch.setattr(embedding_pipeline, "get_mongo_db", lambda: fake)
    return fake


@pytest.fixture
def store(monkeypatch):
    fake = FakeVectorStore()
    monkeypatch.setattr(embedding_pipeline.vector_store, "upsert", fake.upsert)
    monkeypatch.setattr(
        embedding_pipeline.vector_store, "set_metadata", fake.set_metadata
    )
    return fake


@pytest.fixture
def embedded(monkeypatch):
    calls: list[list[str]] = []

    def fake_embed(texts):
        calls.append(list(texts))
        return [[float(len(t)), 0.0, 1.0] for t in texts]

    monkeypatch.setattr(embedding_pipeline, "embed_texts", fake_embed)
    return calls


def make_tenant(sync_session, url_type=URLType.PRICING) -> dict:
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
        url = MonitoredURL(
            competitor_id=comp.id,
            url=f"https://example.com/{suffix}",
            url_type=url_type,
        )
        db.add(url)
        db.commit()
        return {"org_id": str(org.id), "url_id": str(url.id), "ws_id": str(ws.id)}


@pytest.fixture
def tenant(sync_session):
    return make_tenant(sync_session)


T0 = datetime(2026, 10, 1, 12, 0, 0)

# each paragraph is past MIN_CHUNK_CHARS, so boundaries depend only on content
PRO = "Pro plan: 20 dollars per month with unlimited projects. " * 9
TEAM = "Team plan: 50 dollars per month for ten members and SSO. " * 9
ENTERPRISE = "Enterprise plan: custom pricing, audit logs, dedicated support. " * 7


def change(mongo, url_id, paragraphs, at, previous_hash=None) -> str:
    snapshot_id = mongo.page_snapshots.insert_one(
        {
            "monitored_url_id": url_id,
            "paragraphs": paragraphs,
            "text": " ".join(paragraphs),
            "scraped_at": at,
        }
    )
    event_id = mongo.change_events.insert_one(
        {
            "monitored_url_id": url_id,
            "snapshot_id": snapshot_id,
            "detected_at": at,
            "previous_hash": previous_hash,
            "embedding_status": "pending",
        }
    )
    return str(event_id)


def chunk_texts(mongo, url_id, *, current):
    return {
        d["text"]
        for d in mongo.page_chunks.find({"monitored_url_id": url_id})
        if (d["removed_at"] is None) == current
    }


def test_first_change_embeds_every_chunk(mongo, store, embedded, tenant):
    event_id = change(mongo, tenant["url_id"], [PRO.strip(), TEAM.strip()], T0)

    result = run_embedding(event_id)

    assert result["status"] == "done"
    assert result["added"] >= 1
    assert result["removed"] == 0
    vectors = store.namespaces[tenant["org_id"]]
    assert len(vectors) == result["added"]
    meta = next(iter(vectors.values()))["metadata"]
    assert meta["workspace_id"] == tenant["ws_id"]
    assert meta["url_type"] == "pricing"
    assert meta["is_current"] is True
    assert meta["removed_at"] == 0
    assert meta["first_seen_at"] == embedding_pipeline._epoch(T0)
    event = mongo.change_events.find_one({"_id": ObjectId(event_id)})
    assert event["embedding_status"] == "done"
    assert event["embedding_stats"] == {
        k: result[k] for k in ("added", "removed", "returned")
    }


def test_unchanged_chunks_are_not_re_embedded(mongo, store, embedded, tenant):
    url_id = tenant["url_id"]
    run_embedding(change(mongo, url_id, [PRO.strip(), TEAM.strip()], T0))
    first_batch = set(embedded[0])

    run_embedding(
        change(
            mongo,
            url_id,
            [PRO.strip(), TEAM.strip(), ENTERPRISE.strip()],
            T0 + timedelta(hours=1),
        )
    )

    assert len(embedded) == 2
    assert not set(embedded[1]) & first_batch  # only new text hit OpenAI
    assert any("Enterprise" in t for t in embedded[1])


def test_removed_chunks_stay_as_history(mongo, store, embedded, tenant):
    url_id, org_id = tenant["url_id"], tenant["org_id"]
    later = T0 + timedelta(days=2)
    run_embedding(change(mongo, url_id, [PRO.strip(), TEAM.strip()], T0))
    removed_text = chunk_texts(mongo, url_id, current=True)

    result = run_embedding(change(mongo, url_id, [ENTERPRISE.strip()], later))

    assert result["removed"] == len(removed_text)
    assert chunk_texts(mongo, url_id, current=False) == removed_text
    assert all("Enterprise" in t for t in store.current_texts(org_id))
    old = [
        v["metadata"]
        for v in store.namespaces[org_id].values()
        if not v["metadata"]["is_current"]
    ]
    assert old and all(m["removed_at"] == embedding_pipeline._epoch(later) for m in old)


def test_returning_chunk_is_reactivated_without_embedding(
    mongo, store, embedded, tenant
):
    url_id, org_id = tenant["url_id"], tenant["org_id"]
    run_embedding(change(mongo, url_id, [PRO.strip()], T0))
    run_embedding(change(mongo, url_id, [TEAM.strip()], T0 + timedelta(hours=1)))
    calls_before = len(embedded)

    result = run_embedding(
        change(mongo, url_id, [PRO.strip()], T0 + timedelta(hours=2))
    )

    assert result["returned"] >= 1
    assert result["added"] == 0
    assert len(embedded) == calls_before
    assert all("Pro plan" in t for t in store.current_texts(org_id))


def test_orgs_get_separate_namespaces(mongo, store, embedded, sync_session, tenant):
    other = make_tenant(sync_session, URLType.BLOG)
    run_embedding(change(mongo, tenant["url_id"], [PRO.strip()], T0))
    run_embedding(change(mongo, other["url_id"], [TEAM.strip()], T0))

    assert set(store.namespaces) == {tenant["org_id"], other["org_id"]}
    assert all("Pro plan" in t for t in store.current_texts(tenant["org_id"]))
    assert all("Team plan" in t for t in store.current_texts(other["org_id"]))


def test_redelivered_event_is_a_noop(mongo, store, embedded, tenant):
    event_id = change(mongo, tenant["url_id"], [PRO.strip()], T0)
    run_embedding(event_id)

    assert run_embedding(event_id) == {"status": "done"}
    assert len(embedded) == 1


def test_older_event_after_newer_is_superseded(mongo, store, embedded, tenant):
    url_id = tenant["url_id"]
    old_event = change(mongo, url_id, [PRO.strip()], T0)
    run_embedding(change(mongo, url_id, [TEAM.strip()], T0 + timedelta(hours=1)))

    assert run_embedding(old_event) == {"status": "superseded"}
    assert all("Team plan" in t for t in store.current_texts(tenant["org_id"]))


def test_deleted_url_is_skipped(mongo, store, embedded, sync_session):
    event_id = change(mongo, str(uuid.uuid4()), [PRO.strip()], T0)

    assert run_embedding(event_id) == {"status": "skipped"}
    assert embedded == []


def test_missing_event_raises(mongo):
    with pytest.raises(ValueError):
        run_embedding(str(ObjectId()))


def test_task_marks_event_failed_on_permanent_error(mongo, store, monkeypatch, tenant):
    def boom(texts):
        raise openai.AuthenticationError(
            "bad key", response=_fake_response(401), body=None
        )

    monkeypatch.setattr(embedding_pipeline, "embed_texts", boom)
    event_id = change(mongo, tenant["url_id"], [PRO.strip()], T0)

    with pytest.raises(openai.AuthenticationError):
        process_change_event.apply(args=[event_id], throw=True)

    event = mongo.change_events.find_one({"_id": ObjectId(event_id)})
    assert event["embedding_status"] == "failed"
    assert "AuthenticationError" in event["embedding_error"]


def test_busy_url_is_left_pending(mongo, store, embedded, tenant, redis):
    url_id = tenant["url_id"]
    event_id = change(mongo, url_id, [PRO.strip()], T0)
    redis.held.add(f"embedding-lock:{url_id}")  # another worker is on this URL

    with pytest.raises(URLBusy):
        run_embedding(event_id)

    assert embedded == []
    event = mongo.change_events.find_one({"_id": ObjectId(event_id)})
    assert event["embedding_status"] == "pending"


def test_lock_is_released_after_success_and_failure(
    mongo, store, embedded, tenant, redis, monkeypatch
):
    run_embedding(change(mongo, tenant["url_id"], [PRO.strip()], T0))
    assert redis.held == set()

    def boom(texts):
        raise RuntimeError("embedding down")

    monkeypatch.setattr(embedding_pipeline, "embed_texts", boom)
    with pytest.raises(RuntimeError):
        run_embedding(
            change(mongo, tenant["url_id"], [TEAM.strip()], T0 + timedelta(hours=1))
        )
    assert redis.held == set()


def test_task_gives_up_on_busy_url_without_failing(
    mongo, store, embedded, tenant, redis
):
    url_id = tenant["url_id"]
    event_id = change(mongo, url_id, [PRO.strip()], T0)
    redis.held.add(f"embedding-lock:{url_id}")

    # eager apply runs each retry inline, so this exhausts max_retries at once
    result = process_change_event.apply(args=[event_id])

    assert result.get() == {"status": "busy"}
    event = mongo.change_events.find_one({"_id": ObjectId(event_id)})
    assert event["embedding_status"] == "pending"  # left for the sweeper


def test_sweeper_claims_only_lost_pending_events(mongo, tenant):
    url_id = tenant["url_id"]
    now = T0 + timedelta(hours=2)
    lost = change(mongo, url_id, [PRO.strip()], now - timedelta(hours=1))
    fresh = change(mongo, url_id, [TEAM.strip()], now - timedelta(minutes=5))
    done = change(mongo, url_id, [ENTERPRISE.strip()], now - timedelta(hours=1))
    mongo.change_events.update_one(
        {"_id": ObjectId(done)}, {"$set": {"embedding_status": "done"}}
    )
    recently_requeued = change(mongo, url_id, [PRO.strip()], now - timedelta(hours=1))
    mongo.change_events.update_one(
        {"_id": ObjectId(recently_requeued)},
        {"$set": {"requeued_at": now - timedelta(minutes=10)}},
    )

    assert claim_stale_events(now) == [lost]
    assert mongo.change_events.find_one({"_id": ObjectId(lost)})["requeued_at"] == now
    # stamped: the next sweep inside the window leaves it alone
    assert claim_stale_events(now + timedelta(minutes=5)) == []
    assert fresh not in claim_stale_events(now + timedelta(minutes=5))


def test_requeue_task_sends_each_claimed_event(mongo, tenant, monkeypatch):
    lost = change(mongo, tenant["url_id"], [PRO.strip()], T0)
    sent = []
    monkeypatch.setattr(
        embedding_tasks.process_change_event,
        "apply_async",
        lambda args, **kw: sent.append(args[0]),
    )

    assert requeue_stale_events.apply().get() == 1
    assert sent == [lost]


def _fake_response(status: int) -> httpx2.Response:
    return httpx2.Response(
        status, request=httpx2.Request("POST", "https://api.openai.com")
    )


def test_first_scrape_is_not_an_insight(mongo, store, embedded, tenant):
    result = run_embedding(change(mongo, tenant["url_id"], [PRO.strip()], T0))

    assert result["insight_id"] is None
    assert mongo.insights.docs == []


def test_change_becomes_an_insight_with_added_and_removed_text(
    mongo, store, embedded, tenant
):
    url_id = tenant["url_id"]
    run_embedding(change(mongo, url_id, [PRO.strip(), TEAM.strip()], T0))
    later = T0 + timedelta(hours=1)
    event_id = change(
        mongo, url_id, [PRO.strip(), ENTERPRISE.strip()], later, previous_hash="h1"
    )

    result = run_embedding(event_id)

    assert result["insight_id"] == event_id
    insight = mongo.insights.find_one({"_id": ObjectId(event_id)})
    assert insight["org_id"] == tenant["org_id"]
    assert insight["workspace_id"] == tenant["ws_id"]
    assert insight["url_type"] == "pricing"
    assert insight["detected_at"] == later
    assert any("Enterprise" in t for t in insight["added"])
    assert any("Team plan" in t for t in insight["removed"])
    assert not any("Pro plan" in t for t in insight["added"] + insight["removed"])
    assert insight["headline"] == "Pricing page changed"
    lines = [line for hunk in insight["diff"] for line in hunk]
    assert any(line["op"] == "added" and "Enterprise" in line["text"] for line in lines)
    assert any(line["op"] == "removed" and "Team plan" in line["text"] for line in lines)
    assert not any(line["op"] != "context" and "Pro plan" in line["text"] for line in lines)
    assert insight["headline_status"] == "pending"


def test_headline_task_is_queued_for_insights(monkeypatch):
    queued = []
    monkeypatch.setattr(
        embedding_tasks, "run_embedding", lambda event_id: {"status": "done", "insight_id": "abc"}
    )
    monkeypatch.setattr(
        embedding_tasks.write_insight_headline,
        "apply_async",
        lambda args, ignore_result: queued.append(args),
    )

    process_change_event.run("ev1")

    assert queued == [["abc"]]

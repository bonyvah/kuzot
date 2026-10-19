import uuid
from datetime import datetime, timedelta

import httpx
import openai
import pytest
from bson import ObjectId
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import Competitor, MonitoredURL, Organization, URLType, Workspace
from app.workers import embedding_pipeline
from app.workers.embedding_pipeline import run_embedding
from app.workers.tasks.embedding import process_change_event


def _matches(doc: dict, query: dict) -> bool:
    for key, cond in query.items():
        value = doc.get(key)
        if isinstance(cond, dict):
            if "$in" in cond and value not in cond["$in"]:
                return False
            if "$gt" in cond and not (value is not None and value > cond["$gt"]):
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


class FakeMongo:
    def __init__(self):
        self.page_snapshots = FakeCollection()
        self.change_events = FakeCollection()
        self.page_chunks = FakeCollection()


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


def change(mongo, url_id, paragraphs, at) -> str:
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


def _fake_response(status: int) -> httpx.Response:
    return httpx.Response(
        status, request=httpx.Request("POST", "https://api.openai.com")
    )

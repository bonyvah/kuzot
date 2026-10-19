from datetime import datetime, timezone

from bson import ObjectId
from sqlalchemy import select

from app.core.config import settings
from app.embedding import vector_store
from app.embedding.chunking import chunk_units, snapshot_units
from app.embedding.embedder import embed_texts
from app.models import Competitor, MonitoredURL, Workspace
from app.workers.db import SyncSession, get_mongo_db
from app.workers.pipeline import utcnow


def _epoch(dt: datetime) -> int:
    # Pinecone metadata filters need numbers; our datetimes are naive UTC
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def _set_event(event_id: ObjectId, **fields) -> None:
    get_mongo_db().change_events.update_one({"_id": event_id}, {"$set": fields})


def _tenant(monitored_url_id: str) -> dict | None:
    with SyncSession() as db:
        row = db.execute(
            select(
                Workspace.org_id,
                Workspace.id,
                Competitor.id,
                MonitoredURL.url,
                MonitoredURL.url_type,
            )
            .join(Competitor, Competitor.id == MonitoredURL.competitor_id)
            .join(Workspace, Workspace.id == Competitor.workspace_id)
            .where(MonitoredURL.id == monitored_url_id)
        ).first()
    if row is None:
        return None
    return {
        "org_id": str(row[0]),
        "workspace_id": str(row[1]),
        "competitor_id": str(row[2]),
        "monitored_url_id": monitored_url_id,
        "url": row[3],
        "url_type": str(row[4]),
    }


def run_embedding(event_id: str) -> dict:
    """Sync one change event into Pinecone: embed new chunks, retire vanished ones.

    Chunks are keyed by (url, content hash), so a chunk that survives an edit keeps
    its vector and its first_seen_at. That history is what timeline queries read.
    """
    mongo = get_mongo_db()
    oid = ObjectId(event_id)
    event = mongo.change_events.find_one({"_id": oid})
    if event is None:
        raise ValueError(f"Change event not found for id: {event_id}")
    if event.get("embedding_status") in ("done", "superseded", "skipped"):
        return {"status": event["embedding_status"]}  # redelivered message

    url_id = event["monitored_url_id"]
    newer_done = mongo.change_events.find_one(
        {
            "monitored_url_id": url_id,
            "embedding_status": "done",
            "detected_at": {"$gt": event["detected_at"]},
        }
    )
    if newer_done is not None:
        # applying an older page state now would mark current chunks as removed
        _set_event(oid, embedding_status="superseded")
        return {"status": "superseded"}

    tenant = _tenant(url_id)
    snapshot = mongo.page_snapshots.find_one({"_id": event["snapshot_id"]})
    if tenant is None or snapshot is None:
        _set_event(oid, embedding_status="skipped")
        return {"status": "skipped"}

    namespace = tenant["org_id"]  # one namespace per org: queries can't cross tenants
    seen_at = snapshot["scraped_at"]
    chunks = {c.hash: c for c in chunk_units(snapshot_units(snapshot))}

    known = {
        doc["chunk_hash"]: doc
        for doc in mongo.page_chunks.find(
            {"monitored_url_id": url_id}, {"chunk_hash": 1, "removed_at": 1}
        )
    }
    new = [c for h, c in chunks.items() if h not in known]
    returned = [h for h in chunks if h in known and known[h]["removed_at"] is not None]
    removed = [
        h for h, d in known.items() if h not in chunks and d["removed_at"] is None
    ]

    # Pinecone first, Mongo after: a retry recomputes the diff from Mongo and
    # re-upserts the same ids, so a crash between the two is harmless
    embeddings = embed_texts([c.text for c in new]) if new else []
    docs = []
    for chunk, values in zip(new, embeddings, strict=True):
        docs.append(
            {
                "_id": vector_store.vector_id(url_id, chunk.hash),
                **tenant,
                "chunk_hash": chunk.hash,
                "text": chunk.text,
                "embedding": values,  # kept so Pinecone can be rebuilt for free
                "embedding_model": settings.OPENAI_EMBEDDING_MODEL,
                "first_seen_at": seen_at,
                "first_snapshot_id": snapshot["_id"],
                "removed_at": None,
                "removed_snapshot_id": None,
            }
        )
    vector_store.upsert([pinecone_record(doc) for doc in docs], namespace)
    vector_store.set_metadata(
        [vector_store.vector_id(url_id, h) for h in removed],
        {"is_current": False, "removed_at": _epoch(seen_at)},
        namespace,
    )
    vector_store.set_metadata(
        [vector_store.vector_id(url_id, h) for h in returned],
        {"is_current": True, "removed_at": 0},
        namespace,
    )

    if docs:
        mongo.page_chunks.insert_many(docs, ordered=False)
    if removed:
        mongo.page_chunks.update_many(
            {"monitored_url_id": url_id, "chunk_hash": {"$in": removed}},
            {"$set": {"removed_at": seen_at, "removed_snapshot_id": snapshot["_id"]}},
        )
    if returned:
        mongo.page_chunks.update_many(
            {"monitored_url_id": url_id, "chunk_hash": {"$in": returned}},
            {"$set": {"removed_at": None, "removed_snapshot_id": None}},
        )

    stats = {"added": len(new), "removed": len(removed), "returned": len(returned)}
    _set_event(
        oid, embedding_status="done", embedded_at=utcnow(), embedding_stats=stats
    )
    return {"status": "done", **stats}


def pinecone_record(doc: dict) -> dict:
    """Vector + filterable metadata for one page_chunks document."""
    removed_at = doc["removed_at"]
    return {
        "id": doc["_id"],
        "values": doc["embedding"],
        "metadata": {
            "workspace_id": doc["workspace_id"],
            "competitor_id": doc["competitor_id"],
            "monitored_url_id": doc["monitored_url_id"],
            "url": doc["url"],
            "url_type": doc["url_type"],
            "text": doc["text"],
            "snapshot_id": str(doc["first_snapshot_id"]),
            "first_seen_at": _epoch(doc["first_seen_at"]),
            # metadata can't hold null: 0 means the chunk is still on the page
            "removed_at": _epoch(removed_at) if removed_at else 0,
            "is_current": removed_at is None,
        },
    }


def mark_failed(event_id: str, error: str) -> None:
    _set_event(
        ObjectId(event_id), embedding_status="failed", embedding_error=error[:1000]
    )

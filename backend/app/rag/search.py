from dataclasses import dataclass
from datetime import datetime, timezone

from app.embedding.embedder import embed_texts
from app.embedding.vector_store import get_index


@dataclass(frozen=True)
class SearchFilters:
    workspace_id: str
    competitor_ids: list[str] | None = None
    url_types: list[str] | None = None
    current_only: bool = False
    changed_since: datetime | None = None  # added or removed at/after this time


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    score: float
    text: str
    competitor_id: str
    monitored_url_id: str
    url: str
    url_type: str
    snapshot_id: str
    first_seen_at: datetime
    removed_at: datetime | None

    @property
    def is_current(self) -> bool:
        return self.removed_at is None


def _epoch(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _from_epoch(value: float) -> datetime:
    # naive UTC, like every other datetime the API returns
    return datetime.fromtimestamp(value, timezone.utc).replace(tzinfo=None)


def build_filter(f: SearchFilters) -> dict:
    # workspace_id is always there: the org namespace isolates tenants, this
    # keeps one workspace's search from seeing another workspace in the org
    clauses: list[dict] = [{"workspace_id": {"$eq": f.workspace_id}}]
    if f.competitor_ids:
        clauses.append({"competitor_id": {"$in": f.competitor_ids}})
    if f.url_types:
        clauses.append({"url_type": {"$in": f.url_types}})
    if f.current_only:
        clauses.append({"is_current": {"$eq": True}})
    if f.changed_since:
        since = _epoch(f.changed_since)
        clauses.append(
            {
                "$or": [
                    {"first_seen_at": {"$gte": since}},
                    {"removed_at": {"$gte": since}},
                ]
            }
        )
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def search(query: str, org_id: str, filters: SearchFilters, top_k: int) -> list[Hit]:
    """Embed the query and return the closest chunks in one org's namespace."""
    vector = embed_texts([query])[0]
    result = get_index().query(
        vector=vector,
        top_k=top_k,
        namespace=org_id,
        filter=build_filter(filters),
        include_metadata=True,
    )
    hits = []
    for match in result.matches:
        meta = match.metadata or {}
        hits.append(
            Hit(
                chunk_id=match.id,
                score=float(match.score),
                text=meta["text"],
                competitor_id=meta["competitor_id"],
                monitored_url_id=meta["monitored_url_id"],
                url=meta["url"],
                url_type=meta["url_type"],
                snapshot_id=meta["snapshot_id"],
                first_seen_at=_from_epoch(meta["first_seen_at"]),
                removed_at=_from_epoch(meta["removed_at"])
                if meta.get("removed_at")
                else None,
            )
        )
    return hits

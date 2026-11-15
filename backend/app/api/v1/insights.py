from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core import storage
from app.core.auth_dependencies import CurrentUser, require_org_role
from app.core.exceptions import CompetitorNotFoundError
from app.crud.competitor import competitor_crud
from app.crud.org_member import org_member_crud
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession, MongoDBDep
from app.insights import reads
from app.models.competitor import Competitor
from app.models.monitored_url import URLType
from app.models.org_member import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.insight import (
    InsightCounts,
    InsightFeed,
    InsightPublic,
    InsightState,
    InsightStatesUpdate,
    InsightStateUpdated,
    MarkReadRequest,
)

router = APIRouter(tags=["Insights"])

PAGE_SIZE = 20


@dataclass
class Reader:
    """The current user as a reader of one organization's insights."""
    user_id: str
    org_id: str
    seen_until: datetime


async def _reader(user: User, org_id: UUID, db: DBSession, mongo: MongoDBDep) -> Reader:
    await require_org_role(user, org_id, MemberRole.MEMBER, db)
    member = await org_member_crud.get_by_user_and_org(db, user_id=user.id, org_id=org_id)
    watermark = await reads.seen_until(mongo, str(user.id), str(org_id), default=member.joined_at)
    return Reader(str(user.id), str(org_id), watermark)


def _decode_cursor(cursor: str) -> tuple[datetime, ObjectId]:
    try:
        stamp, oid = cursor.split("|", 1)
        return datetime.fromisoformat(stamp), ObjectId(oid)
    except (ValueError, InvalidId):
        raise HTTPException(status_code=400, detail="Invalid cursor")


def _encode_cursor(doc: dict) -> str:
    return f"{doc['detected_at'].isoformat()}|{doc['_id']}"


async def _competitor_names(db: DBSession, competitor_ids: set[UUID]) -> dict[str, dict]:
    """Display fields per competitor id; deleted competitors are missing."""
    if not competitor_ids:
        return {}
    rows = (
        await db.execute(
            select(Competitor.id, Competitor.name, Competitor.avatar_emoji, Competitor.avatar_key, Workspace.name)
            .join(Workspace, Workspace.id == Competitor.workspace_id)
            .where(Competitor.id.in_(competitor_ids))
        )
    ).all()
    return {
        str(c_id): {
            "competitor_name": c_name,
            "competitor_avatar_emoji": emoji,
            "competitor_avatar_url": storage.public_url(key) if key else None,
            "workspace_name": w_name,
        }
        for c_id, c_name, emoji, key, w_name in rows
    }


async def _feed(
    mongo: MongoDBDep,
    db: DBSession,
    reader: Reader,
    scope: dict,
    *,
    state: reads.FeedState,
    min_severity: reads.MinSeverity | None,
    cursor: str | None,
    limit: int,
    url_types: list[URLType] | None,
    competitor_id: UUID | None = None,
    workspace_id: UUID | None = None,
) -> InsightFeed:
    query: dict = dict(scope)
    if url_types:
        query["url_type"] = {"$in": [str(t) for t in url_types]}
    if competitor_id:
        query["competitor_id"] = str(competitor_id)
    if workspace_id:
        query["workspace_id"] = str(workspace_id)
    query |= await reads.feed_filter(mongo, reader.user_id, reader.org_id, reader.seen_until, state)
    query |= reads.severity_filter(min_severity)
    if cursor:
        # newest first; ties on the timestamp are broken by id
        at, oid = _decode_cursor(cursor)
        query["$or"] = [
            {"detected_at": {"$lt": at}},
            {"detected_at": at, "_id": {"$lt": oid}},
        ]

    docs = [
        d
        async for d in mongo.insights.find(query)
        .sort([("detected_at", -1), ("_id", -1)])
        .limit(limit + 1)
    ]
    more = len(docs) > limit
    docs = docs[:limit]

    # names come from Postgres; insights of deleted competitors are dropped
    names = await _competitor_names(db, {UUID(d["competitor_id"]) for d in docs})
    states = await reads.states_for(mongo, reader.user_id, docs, reader.seen_until)

    items = [
        InsightPublic(
            **{k: v for k, v in d.items() if k != "_id"},
            id=str(d["_id"]),
            **names[d["competitor_id"]],
            state=InsightState(**states[str(d["_id"])]),
        )
        for d in docs
        if d["competitor_id"] in names
    ]
    return InsightFeed(items=items, next_cursor=_encode_cursor(docs[-1]) if more else None)


Limit = Query(PAGE_SIZE, ge=1, le=100)
Types = Query(None, alias="url_type")
State = Query("all", description="all: everything not dismissed; unread; saved")
Importance = Query(None, description="only insights at least this important")


@router.get("/organizations/{org_id}/insights", response_model=InsightFeed)
async def org_insights(
    org_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
    cursor: str | None = None,
    limit: int = Limit,
    url_types: list[URLType] | None = Types,
    workspace_id: UUID | None = None,
    competitor_id: UUID | None = None,
    state: reads.FeedState = State,
    min_severity: reads.MinSeverity | None = Importance,
):
    reader = await _reader(current_user, org_id, db, mongo)
    return await _feed(
        mongo, db, reader, {"org_id": str(org_id)}, state=state, min_severity=min_severity, cursor=cursor, limit=limit,
        url_types=url_types, workspace_id=workspace_id, competitor_id=competitor_id,
    )


@router.get("/workspaces/{workspace_id}/insights", response_model=InsightFeed)
async def workspace_insights(
    workspace_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
    cursor: str | None = None,
    limit: int = Limit,
    url_types: list[URLType] | None = Types,
    competitor_id: UUID | None = None,
    state: reads.FeedState = State,
    min_severity: reads.MinSeverity | None = Importance,
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    reader = await _reader(current_user, workspace.org_id, db, mongo)
    return await _feed(
        mongo, db, reader, {"workspace_id": str(workspace_id)}, state=state, min_severity=min_severity, cursor=cursor, limit=limit,
        url_types=url_types, competitor_id=competitor_id,
    )


@router.get("/competitors/{competitor_id}/insights", response_model=InsightFeed)
async def competitor_insights(
    competitor_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
    cursor: str | None = None,
    limit: int = Limit,
    url_types: list[URLType] | None = Types,
    state: reads.FeedState = State,
    min_severity: reads.MinSeverity | None = Importance,
):
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    reader = await _reader(current_user, workspace.org_id, db, mongo)
    return await _feed(
        mongo, db, reader, {"competitor_id": str(competitor_id)}, state=state, min_severity=min_severity, cursor=cursor, limit=limit,
        url_types=url_types,
    )


# ── Read state ───────────────────────────────────────────────────────────────


async def _counts(
    mongo: MongoDBDep, db: DBSession, reader: Reader, min_severity: reads.MinSeverity | None = None
) -> InsightCounts:
    per_pair = await reads.unread_counts(mongo, reader.user_id, reader.org_id, reader.seen_until, min_severity)
    # insights of deleted competitors aren't shown, so they don't count
    live = await _competitor_names(db, {UUID(c) for _, c in per_pair})
    workspaces: dict[str, int] = {}
    competitors: dict[str, int] = {}
    for (w, c), n in per_pair.items():
        if c not in live:
            continue
        workspaces[w] = workspaces.get(w, 0) + n
        competitors[c] = competitors.get(c, 0) + n
    return InsightCounts(total=sum(competitors.values()), workspaces=workspaces, competitors=competitors)


@router.get("/organizations/{org_id}/insights/counts", response_model=InsightCounts)
async def unread_counts(
    org_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
    min_severity: reads.MinSeverity | None = Importance,
):
    reader = await _reader(current_user, org_id, db, mongo)
    return await _counts(mongo, db, reader, min_severity)


@router.post("/organizations/{org_id}/insights/read", response_model=InsightCounts)
async def mark_read(
    org_id: UUID, body: MarkReadRequest, current_user: CurrentUser, db: DBSession, mongo: MongoDBDep
):
    """Mark everything read: the whole organization, or one workspace or competitor."""
    reader = await _reader(current_user, org_id, db, mongo)
    now = reads.utcnow()
    if body.workspace_id is None and body.competitor_id is None and body.min_severity is None:
        await reads.set_seen_until(mongo, reader.user_id, reader.org_id, now)
        reader.seen_until = now
    else:
        query: dict = {"org_id": reader.org_id}
        if body.workspace_id:
            query["workspace_id"] = str(body.workspace_id)
        if body.competitor_id:
            query["competitor_id"] = str(body.competitor_id)
        query |= await reads.feed_filter(mongo, reader.user_id, reader.org_id, reader.seen_until, "unread")
        query |= reads.severity_filter(body.min_severity)
        docs = [d async for d in mongo.insights.find(
            query, {"org_id": 1, "workspace_id": 1, "competitor_id": 1, "detected_at": 1}
        )]
        await reads.apply(mongo, reader.user_id, docs, "seen", now)
    return await _counts(mongo, db, reader, body.min_severity)


@router.post("/insights/states", response_model=list[InsightStateUpdated])
async def update_states(body: InsightStatesUpdate, current_user: CurrentUser, db: DBSession, mongo: MongoDBDep):
    """Seen, opened, saved or dismissed, for up to 100 insights at once."""
    try:
        oids = [ObjectId(i) for i in body.ids]
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid insight id")
    docs = [d async for d in mongo.insights.find({"_id": {"$in": oids}})]
    if len(docs) != len(set(oids)):
        raise HTTPException(status_code=404, detail="Insight not found")

    out: list[InsightStateUpdated] = []
    for org_id in sorted({d["org_id"] for d in docs}):
        group = [d for d in docs if d["org_id"] == org_id]
        reader = await _reader(current_user, UUID(org_id), db, mongo)
        await reads.apply(mongo, reader.user_id, group, body.action, reads.utcnow())
        states = await reads.states_for(mongo, reader.user_id, group, reader.seen_until)
        out += [InsightStateUpdated(id=i, state=InsightState(**s)) for i, s in states.items()]
    return out

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
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession, MongoDBDep
from app.models.competitor import Competitor
from app.models.monitored_url import URLType
from app.models.org_member import MemberRole
from app.models.workspace import Workspace
from app.schemas.insight import InsightFeed, InsightPublic

router = APIRouter(tags=["Insights"])

PAGE_SIZE = 20


def _decode_cursor(cursor: str) -> tuple[datetime, ObjectId]:
    try:
        stamp, oid = cursor.split("|", 1)
        return datetime.fromisoformat(stamp), ObjectId(oid)
    except (ValueError, InvalidId):
        raise HTTPException(status_code=400, detail="Invalid cursor")


def _encode_cursor(doc: dict) -> str:
    return f"{doc['detected_at'].isoformat()}|{doc['_id']}"


async def _feed(
    mongo: MongoDBDep,
    db: DBSession,
    scope: dict,
    *,
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
    competitor_ids = {UUID(d["competitor_id"]) for d in docs}
    rows = (
        await db.execute(
            select(Competitor.id, Competitor.name, Competitor.avatar_emoji, Competitor.avatar_key, Workspace.name)
            .join(Workspace, Workspace.id == Competitor.workspace_id)
            .where(Competitor.id.in_(competitor_ids))
        )
    ).all() if competitor_ids else []
    names = {
        str(c_id): {
            "competitor_name": c_name,
            "competitor_avatar_emoji": emoji,
            "competitor_avatar_url": storage.public_url(key) if key else None,
            "workspace_name": w_name,
        }
        for c_id, c_name, emoji, key, w_name in rows
    }

    items = [
        InsightPublic(
            **{k: v for k, v in d.items() if k != "_id"},
            id=str(d["_id"]),
            **names[d["competitor_id"]],
        )
        for d in docs
        if d["competitor_id"] in names
    ]
    return InsightFeed(items=items, next_cursor=_encode_cursor(docs[-1]) if more else None)


Limit = Query(PAGE_SIZE, ge=1, le=100)
Types = Query(None, alias="url_type")


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
):
    await require_org_role(current_user, org_id, MemberRole.MEMBER, db)
    return await _feed(
        mongo, db, {"org_id": str(org_id)}, cursor=cursor, limit=limit,
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
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)
    return await _feed(
        mongo, db, {"workspace_id": str(workspace_id)}, cursor=cursor, limit=limit,
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
):
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)
    return await _feed(
        mongo, db, {"competitor_id": str(competitor_id)}, cursor=cursor, limit=limit,
        url_types=url_types,
    )

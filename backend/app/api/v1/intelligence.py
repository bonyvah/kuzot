import math
from datetime import datetime, timezone
from uuid import UUID

import openai
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pinecone.errors import PineconeError
from sqlalchemy import select

from app.core.auth_dependencies import CurrentUser, require_org_role
from app.core.exceptions import AIServiceError
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession, MongoDBDep
from app.models.competitor import Competitor
from app.models.org_member import MemberRole
from app.models.workspace import Workspace
from app.rag.reports import generate_report
from app.rag.search import Hit, SearchFilters, search
from app.schemas.common import PaginatedResponse
from app.schemas.intelligence import (
    ReportPublic,
    ReportRequest,
    ReportSummary,
    SearchHit,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(tags=["Search & Reports"])

AI_ERRORS = (openai.OpenAIError, PineconeError)


async def _workspace_for_member(
    db: DBSession, workspace_id: UUID, current_user: CurrentUser
) -> Workspace:
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)
    return workspace


async def _competitor_names(db: DBSession, workspace_id: UUID) -> dict[str, str]:
    result = await db.execute(
        select(Competitor.id, Competitor.name).where(
            Competitor.workspace_id == workspace_id
        )
    )
    return {str(id_): name for id_, name in result.all()}


async def _search(
    workspace: Workspace,
    query: str,
    *,
    competitor_ids: list[UUID] | None,
    url_types: list | None,
    current_only: bool,
    changed_since: datetime | None,
    top_k: int,
) -> list[Hit]:
    filters = SearchFilters(
        workspace_id=str(workspace.id),
        competitor_ids=[str(c) for c in competitor_ids] if competitor_ids else None,
        url_types=[str(t) for t in url_types] if url_types else None,
        current_only=current_only,
        changed_since=changed_since,
    )
    # OpenAI + Pinecone clients are blocking: keep them off the event loop
    try:
        return await run_in_threadpool(
            search, query, str(workspace.org_id), filters, top_k
        )
    except AI_ERRORS as exc:
        raise AIServiceError(type(exc).__name__)


def _hit_out(hit: Hit, names: dict[str, str]) -> dict:
    return {
        "chunk_id": hit.chunk_id,
        "score": hit.score,
        "text": hit.text,
        "competitor_id": hit.competitor_id,
        "competitor_name": names.get(hit.competitor_id, "Unknown"),
        "monitored_url_id": hit.monitored_url_id,
        "url": hit.url,
        "url_type": hit.url_type,
        "snapshot_id": hit.snapshot_id,
        "first_seen_at": hit.first_seen_at,
        "removed_at": hit.removed_at,
        "is_current": hit.is_current,
    }


def _report_out(doc: dict) -> ReportPublic:
    return ReportPublic.model_validate({**doc, "id": str(doc["_id"])})


@router.post("/workspaces/{workspace_id}/search", response_model=SearchResponse)
async def semantic_search(
    workspace_id: UUID,
    body: SearchRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    workspace = await _workspace_for_member(db, workspace_id, current_user)
    hits = await _search(
        workspace,
        body.query,
        competitor_ids=body.competitor_ids,
        url_types=body.url_types,
        current_only=body.scope == "current",
        changed_since=body.changed_since,
        top_k=body.top_k,
    )
    names = await _competitor_names(db, workspace.id)
    return SearchResponse(
        query=body.query,
        hits=[SearchHit(**_hit_out(h, names)) for h in hits],
    )


@router.post(
    "/workspaces/{workspace_id}/reports",
    response_model=ReportPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    workspace_id: UUID,
    body: ReportRequest,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
):
    workspace = await _workspace_for_member(db, workspace_id, current_user)
    # current and removed text both go in: removed chunks are how the model
    # sees what changed
    hits = await _search(
        workspace,
        body.prompt,
        competitor_ids=body.competitor_ids,
        url_types=body.url_types,
        current_only=False,
        changed_since=body.changed_since,
        top_k=body.top_k,
    )
    if not hits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No competitor content matches this request yet",
        )

    names = await _competitor_names(db, workspace.id)
    try:
        report = await run_in_threadpool(generate_report, body.prompt, hits, names)
    except openai.OpenAIError as exc:
        raise AIServiceError(type(exc).__name__)

    doc = {
        "workspace_id": str(workspace.id),
        "org_id": str(workspace.org_id),
        "prompt": body.prompt,
        "content": report.content,
        "model": report.model,
        "sources": [
            {**_hit_out(h, names), "number": i, "cited": i in report.cited}
            for i, h in enumerate(hits, start=1)
        ],
        "filters": body.model_dump(mode="json", exclude={"prompt"}),
        "created_by_user_id": str(current_user.id),
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    result = await mongo.reports.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _report_out(doc)


@router.get(
    "/workspaces/{workspace_id}/reports",
    response_model=PaginatedResponse[ReportSummary],
)
async def list_reports(
    workspace_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    workspace = await _workspace_for_member(db, workspace_id, current_user)
    query = {"workspace_id": str(workspace.id)}
    total = await mongo.reports.count_documents(query)
    cursor = (
        mongo.reports.find(query, {"content": 0, "sources": 0})
        .sort("created_at", -1)
        .skip((page - 1) * size)
        .limit(size)
    )
    items = [
        ReportSummary.model_validate({**d, "id": str(d["_id"])})
        async for d in cursor
    ]
    return PaginatedResponse[ReportSummary](
        items=items,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 1,
    )


@router.get("/reports/{report_id}", response_model=ReportPublic)
async def get_report(
    report_id: str,
    current_user: CurrentUser,
    db: DBSession,
    mongo: MongoDBDep,
):
    try:
        oid = ObjectId(report_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Report not found")
    doc = await mongo.reports.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Report not found")
    await _workspace_for_member(db, UUID(doc["workspace_id"]), current_user)
    return _report_out(doc)

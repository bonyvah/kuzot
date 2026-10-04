import math
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.core.auth_dependencies import CurrentUser, require_org_role
from app.core.exceptions import CompetitorNotFoundError, MonitoredURLNotFoundError
from app.crud.competitor import competitor_crud
from app.crud.monitored_url import monitored_url_crud
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession
from app.models.org_member import MemberRole
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.competitor import (
    CompetitorCreate,
    CompetitorPublic,
    CompetitorUpdate,
    MonitoredURLCreate,
    MonitoredURLPublic,
)

router = APIRouter(tags=["Competitors"])


@router.post(
    "/workspaces/{workspace_id}/competitors",
    response_model=CompetitorPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_competitor(
    workspace_id: UUID,
    body: CompetitorCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    return await competitor_crud.create(db, workspace_id=workspace_id, obj_in=body)


@router.get(
    "/workspaces/{workspace_id}/competitors",
    response_model=PaginatedResponse[CompetitorPublic],
)
async def list_competitors(
    workspace_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    skip = (page - 1) * size
    items, total = await competitor_crud.list_by_workspace(db, workspace_id=workspace_id, skip=skip, limit=size)
    pages = math.ceil(total / size) if total > 0 else 1

    return PaginatedResponse[CompetitorPublic](
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/competitors/{competitor_id}", response_model=CompetitorPublic)
async def get_competitor(
    competitor_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    return competitor


@router.put("/competitors/{competitor_id}", response_model=CompetitorPublic)
async def update_competitor(
    competitor_id: UUID,
    body: CompetitorUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    return await competitor_crud.update(db, competitor, body)


@router.delete("/competitors/{competitor_id}", response_model=MessageResponse)
async def delete_competitor(
    competitor_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    await competitor_crud.delete(db, competitor)
    return MessageResponse(message="Competitor deleted successfully")


# ── Monitored URLs ─────────────────────────────────────────────────────────────

@router.post(
    "/competitors/{competitor_id}/urls",
    response_model=MonitoredURLPublic,
    status_code=status.HTTP_201_CREATED,
)
async def add_monitored_url(
    competitor_id: UUID,
    body: MonitoredURLCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    return await monitored_url_crud.create(db, competitor_id=competitor_id, obj_in=body)


@router.delete("/monitored-urls/{url_id}", response_model=MessageResponse)
async def delete_monitored_url(
    url_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    monitored_url = await monitored_url_crud.get_by_id(db, url_id)
    if not monitored_url:
        raise MonitoredURLNotFoundError(str(url_id))

    competitor = await competitor_crud.get_by_id(db, monitored_url.competitor_id)
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    await monitored_url_crud.delete(db, monitored_url)
    return MessageResponse(message="Monitored URL deleted successfully")

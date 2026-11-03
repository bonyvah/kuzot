from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.core.auth_dependencies import CurrentUser, require_org_role
from app.core.exceptions import CompetitorNotFoundError
from app.crud.competitor import competitor_crud
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession
from app.discovery import search
from app.discovery.service import Discovery, Hint, discover
from app.models.org_member import MemberRole
from app.schemas.discovery import DiscoveredPage, DiscoverRequest, DiscoverResponse, FindPageRequest

router = APIRouter(tags=["Discovery"])


def _response(result: Discovery) -> DiscoverResponse:
    return DiscoverResponse(
        pages=[DiscoveredPage(**asdict(p)) for p in result.pages],
        notes=result.notes,
        search_enabled=search.enabled(),
    )


@router.post("/workspaces/{workspace_id}/discover", response_model=DiscoverResponse)
async def discover_competitor_pages(
    workspace_id: UUID,
    body: DiscoverRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Suggest pages to monitor for a competitor that's being added."""
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    # fetching, searching and the model call are blocking: keep them off the loop
    result = await run_in_threadpool(
        lambda: discover(
            name=body.name,
            website=body.website,
            description=body.description,
            notes=body.notes,
            hints=[Hint(h.url_type, h.value, h.label) for h in body.hints],
        )
    )
    return _response(result)


@router.post("/competitors/{competitor_id}/discover", response_model=DiscoverResponse)
async def find_competitor_page(
    competitor_id: UUID,
    body: FindPageRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Suggest a page for an existing competitor, e.g. "their pricing page"."""
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))
    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    result = await run_in_threadpool(
        lambda: discover(
            name=competitor.name,
            website=competitor.website_url,
            description=competitor.description,
            looking_for=body.looking_for,
            hints=[Hint(h.url_type, h.value, h.label) for h in body.hints],
            exclude={u.url for u in competitor.urls},
        )
    )
    return _response(result)

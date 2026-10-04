from uuid import UUID
from fastapi import APIRouter, HTTPException, status

from app.core.auth_dependencies import CurrentUser, require_org_role
from app.crud.organization import organization_crud
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession
from app.models.org_member import MemberRole
from app.schemas.common import MessageResponse
from app.schemas.workspace import WorkspaceCreate, WorkspacePublic, WorkspaceUpdate

router = APIRouter(tags=["Workspaces"])


@router.post(
    "/organizations/{org_id}/workspaces",
    response_model=WorkspacePublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    org_id: UUID,
    body: WorkspaceCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.MEMBER, db)
    return await workspace_crud.create(db, org_id=org_id, obj_in=body, user_id=current_user.id)


@router.get(
    "/organizations/{org_id}/workspaces",
    response_model=list[WorkspacePublic],
)
async def list_workspaces(
    org_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.MEMBER, db)
    return await workspace_crud.list_by_org(db, org_id=org_id)


@router.get("/workspaces/{workspace_id}", response_model=WorkspacePublic)
async def get_workspace(
    workspace_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)
    return workspace


@router.put("/workspaces/{workspace_id}", response_model=WorkspacePublic)
async def update_workspace(
    workspace_id: UUID,
    body: WorkspaceUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.ADMIN, db)
    return await workspace_crud.update(db, workspace, body)


@router.delete("/workspaces/{workspace_id}", response_model=MessageResponse)
async def delete_workspace(
    workspace_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    workspace = await workspace_crud.get_by_id(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_org_role(current_user, workspace.org_id, MemberRole.ADMIN, db)
    await workspace_crud.delete(db, workspace)
    return MessageResponse(message="Workspace deleted successfully")

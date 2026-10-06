from uuid import UUID
from fastapi import APIRouter, HTTPException, status

from app.core.auth_dependencies import CurrentUser, require_org_role
from app.crud.organization import organization_crud
from app.crud.org_member import org_member_crud
from app.crud.user import user_crud
from app.db.dependencies import DBSession
from app.models.org_member import MemberRole
from app.schemas.common import MessageResponse
from app.schemas.organization import (
    InviteMemberRequest,
    OrgCreate,
    OrgMemberPublic,
    OrgPublic,
    OrgUpdate,
    UpdateMemberRoleRequest,
)

from app.models.organization import OrgType

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("/", response_model=OrgPublic, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    if body.org_type == OrgType.PERSONAL:
        existing_personal = await organization_crud.get_user_personal_org(db, user_id=current_user.id)
        if existing_personal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a personal organization. Maximum 1 personal organization allowed.",
            )

    return await organization_crud.create(db, obj_in=body, user_id=current_user.id)


@router.get("/", response_model=list[OrgPublic])
async def list_user_organizations(
    current_user: CurrentUser,
    db: DBSession,
):
    return await organization_crud.list_user_orgs(db, user_id=current_user.id)


@router.get("/{org_id}", response_model=OrgPublic)
async def get_organization(
    org_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.MEMBER, db)
    org = await organization_crud.get_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/{org_id}", response_model=OrgPublic)
async def update_organization(
    org_id: UUID,
    body: OrgUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.ADMIN, db)
    org = await organization_crud.get_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return await organization_crud.update(db, org, body)


@router.delete("/{org_id}", response_model=MessageResponse)
async def delete_organization(
    org_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.OWNER, db)
    org = await organization_crud.get_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    await organization_crud.delete(db, org)
    return MessageResponse(message="Organization deleted successfully")


# ── Members Management ─────────────────────────────────────────────────────────

@router.get("/{org_id}/members", response_model=list[OrgMemberPublic])
async def list_org_members(
    org_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.MEMBER, db)
    return await org_member_crud.list_by_org(db, org_id)


@router.post("/{org_id}/members", response_model=OrgMemberPublic, status_code=status.HTTP_201_CREATED)
async def add_org_member(
    org_id: UUID,
    body: InviteMemberRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.ADMIN, db)
    org = await organization_crud.get_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if org.org_type == OrgType.PERSONAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Personal organizations cannot have additional members",
        )

    user_to_add = await user_crud.get_by_id(db, body.user_id)
    if not user_to_add:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await org_member_crud.get_by_user_and_org(db, user_id=body.user_id, org_id=org_id)
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member of this organization")

    return await org_member_crud.add_member(db, org_id=org_id, user_id=body.user_id, role=body.role)


@router.put("/{org_id}/members/{user_id}", response_model=OrgMemberPublic)
async def update_org_member_role(
    org_id: UUID,
    user_id: UUID,
    body: UpdateMemberRoleRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.OWNER, db)
    member = await org_member_crud.get_by_user_and_org(db, user_id=user_id, org_id=org_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in organization")

    return await org_member_crud.update_role(db, member, new_role=body.role)


@router.delete("/{org_id}/members/{user_id}", response_model=MessageResponse)
async def remove_org_member(
    org_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_org_role(current_user, org_id, MemberRole.OWNER, db)
    member = await org_member_crud.get_by_user_and_org(db, user_id=user_id, org_id=org_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in organization")

    await org_member_crud.remove_member(db, member)
    return MessageResponse(message="Member removed successfully")

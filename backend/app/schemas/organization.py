from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.organization import OrgPlan, OrgType
from app.models.org_member import MemberRole


class OrgCreate(BaseModel):
    name: str
    org_type: OrgType = OrgType.TEAM


class OrgUpdate(BaseModel):
    name: str | None = None


class OrgPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    org_type: OrgType
    plan: OrgPlan
    created_at: datetime
    updated_at: datetime


class OrgMemberPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    user_id: UUID
    role: MemberRole
    joined_at: datetime


class InviteMemberRequest(BaseModel):
    user_id: UUID
    role: MemberRole = MemberRole.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    role: MemberRole

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.core import storage
from app.models.organization import OrgPlan, OrgType
from app.models.org_member import MemberRole
from app.services.avatars import validate_emoji


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
    avatar_emoji: str | None = None
    avatar_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _avatar_url(cls, data):
        # the stored S3 key becomes the URL browsers load
        key = getattr(data, "avatar_key", None)
        if key is not None:
            data = {name: getattr(data, name) for name in cls.model_fields if hasattr(data, name)}
            data["avatar_url"] = storage.public_url(key)
        return data


class AvatarEmoji(BaseModel):
    emoji: str

    @field_validator("emoji")
    @classmethod
    def _valid(cls, value: str) -> str:
        return validate_emoji(value)


class OrgMemberPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    user_id: UUID
    email: str
    full_name: str | None
    role: MemberRole
    joined_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _flatten_user(cls, data):
        # OrgMember rows carry the user as a relationship; expose who it is
        if hasattr(data, "user"):
            return {
                "id": data.id,
                "org_id": data.org_id,
                "user_id": data.user_id,
                "email": data.user.email,
                "full_name": data.user.full_name,
                "role": data.role,
                "joined_at": data.joined_at,
            }
        return data


class InviteMemberRequest(BaseModel):
    """Add an existing user to the org, by email or by user id."""

    email: EmailStr | None = None
    user_id: UUID | None = None
    role: MemberRole = MemberRole.MEMBER

    @model_validator(mode="after")
    def _one_identifier(self):
        if (self.email is None) == (self.user_id is None):
            raise ValueError("Provide exactly one of email or user_id")
        return self


class UpdateMemberRoleRequest(BaseModel):
    role: MemberRole

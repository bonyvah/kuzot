from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core import storage


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class WorkspacePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    description: str | None
    created_by_user_id: UUID | None
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

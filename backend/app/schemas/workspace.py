from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.avatar import WithAvatar


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class WorkspacePublic(WithAvatar):

    id: UUID
    org_id: UUID
    name: str
    description: str | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

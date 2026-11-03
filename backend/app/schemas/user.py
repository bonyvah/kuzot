from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.schemas.avatar import WithAvatar


class UserPublic(WithAvatar):
    id: UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None

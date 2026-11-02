from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.monitored_url import URLType


class InsightPublic(BaseModel):
    id: str
    org_id: UUID
    workspace_id: UUID
    workspace_name: str
    competitor_id: UUID
    competitor_name: str
    monitored_url_id: UUID
    url: str
    url_type: URLType
    label: str | None
    detected_at: datetime
    headline: str
    # pending: the AI headline isn't written yet and `headline` is a fallback
    headline_status: Literal["pending", "done", "failed"]
    added: list[str]
    removed: list[str]
    added_count: int
    removed_count: int


class InsightFeed(BaseModel):
    items: list[InsightPublic]
    # pass as ?cursor= to get the next (older) page; null at the end
    next_cursor: str | None

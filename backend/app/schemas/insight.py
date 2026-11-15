from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.monitored_url import URLType


class DiffLine(BaseModel):
    op: Literal["context", "removed", "added"]
    text: str


class InsightState(BaseModel):
    """What the current user did with an insight."""
    seen: bool = False
    opened: bool = False
    saved: bool = False
    dismissed: bool = False


class InsightPublic(BaseModel):
    id: str
    # monitoring_started: the page was just added; no diff, only the headline
    kind: Literal["change", "monitoring_started"] = "change"
    org_id: UUID
    workspace_id: UUID
    workspace_name: str
    competitor_id: UUID
    competitor_name: str
    competitor_avatar_emoji: str | None = None
    competitor_avatar_url: str | None = None
    monitored_url_id: UUID
    url: str
    url_type: URLType
    label: str | None
    detected_at: datetime
    headline: str
    # pending: the AI headline isn't written yet and `headline` is a fallback
    headline_status: Literal["pending", "done", "failed"]
    # changed lines with a little context, in hunks; empty for older insights
    diff: list[list[DiffLine]] = []
    added: list[str]
    removed: list[str]
    added_count: int
    removed_count: int
    state: InsightState = InsightState()


class InsightFeed(BaseModel):
    items: list[InsightPublic]
    # pass as ?cursor= to get the next (older) page; null at the end
    next_cursor: str | None


class InsightCounts(BaseModel):
    """Unread insights for the current user, overall and per workspace / competitor."""
    total: int
    workspaces: dict[str, int]
    competitors: dict[str, int]


class InsightStatesUpdate(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
    action: Literal["seen", "open", "save", "unsave", "dismiss", "restore"]


class InsightStateUpdated(BaseModel):
    id: str
    state: InsightState


class MarkReadRequest(BaseModel):
    # neither: the whole organization
    workspace_id: UUID | None = None
    competitor_id: UUID | None = None

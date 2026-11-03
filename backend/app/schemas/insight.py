from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.monitored_url import URLType


class DiffLine(BaseModel):
    op: Literal["context", "removed", "added"]
    text: str


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


class InsightFeed(BaseModel):
    items: list[InsightPublic]
    # pass as ?cursor= to get the next (older) page; null at the end
    next_cursor: str | None

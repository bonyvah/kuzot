from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.monitored_url import URLType


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    competitor_ids: list[UUID] | None = None
    url_types: list[URLType] | None = None
    # current: what competitors say now; all: include removed text (history)
    scope: Literal["current", "all"] = "current"
    changed_since: datetime | None = None
    top_k: int = Field(10, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: str
    score: float
    text: str
    competitor_id: UUID
    competitor_name: str
    monitored_url_id: UUID
    url: str
    url_type: URLType
    snapshot_id: str
    first_seen_at: datetime
    removed_at: datetime | None
    is_current: bool


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class ReportRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    competitor_ids: list[UUID] | None = None
    url_types: list[URLType] | None = None
    changed_since: datetime | None = None
    top_k: int = Field(20, ge=1, le=50)


class ReportSource(SearchHit):
    number: int  # the [n] the report cites
    cited: bool


class ReportPublic(BaseModel):
    id: str
    workspace_id: UUID
    prompt: str
    content: str
    model: str
    sources: list[ReportSource]
    filters: dict
    created_by_user_id: UUID
    created_at: datetime


class ReportSummary(BaseModel):
    id: str
    prompt: str
    model: str
    created_by_user_id: UUID
    created_at: datetime

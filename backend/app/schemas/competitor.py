from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.models.monitored_url import URLType


class MonitoredURLCreate(BaseModel):
    url: str
    url_type: URLType = URLType.HOMEPAGE
    scrape_interval_minutes: int | None = 60


class MonitoredURLPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    competitor_id: UUID
    url: str
    url_type: URLType
    scrape_interval_minutes: int | None
    last_scraped_at: datetime | None
    last_content_hash: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompetitorCreate(BaseModel):
    name: str
    description: str | None = None
    website_url: str | None = None
    initial_urls: list[MonitoredURLCreate] = []


class CompetitorUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    website_url: str | None = None
    is_active: bool | None = None


class CompetitorPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    website_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    urls: list[MonitoredURLPublic] = []

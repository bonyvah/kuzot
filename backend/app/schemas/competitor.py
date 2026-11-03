from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.monitored_url import URLType
from app.schemas.avatar import WithAvatar


# Scrape intervals: anything from 15 minutes to 30 days, daily by default.
# None means "manual scrapes only".
MIN_INTERVAL_MINUTES = 15
MAX_INTERVAL_MINUTES = 30 * 24 * 60
DEFAULT_INTERVAL_MINUTES = 24 * 60

Interval = Field(default=DEFAULT_INTERVAL_MINUTES, ge=MIN_INTERVAL_MINUTES, le=MAX_INTERVAL_MINUTES)


def _check_label(url_type: URLType | None, label: str | None) -> str | None:
    """OTHER pages need a label saying what they are; other types don't keep one."""
    if url_type != URLType.OTHER:
        return None
    label = (label or "").strip()
    if not label:
        raise ValueError("Describe what this page is, e.g. LinkedIn")
    return label


class MonitoredURLCreate(BaseModel):
    url: str
    url_type: URLType = URLType.HOMEPAGE
    label: str | None = Field(default=None, max_length=100)
    scrape_interval_minutes: int | None = Interval

    @model_validator(mode="after")
    def _label(self):
        self.label = _check_label(self.url_type, self.label)
        return self


class MonitoredURLUpdate(BaseModel):
    """Fields left out are unchanged; scrape_interval_minutes=null means manual only."""

    url_type: URLType | None = None
    label: str | None = Field(default=None, max_length=100)
    scrape_interval_minutes: int | None = Field(
        default=None, ge=MIN_INTERVAL_MINUTES, le=MAX_INTERVAL_MINUTES
    )
    is_active: bool | None = None


class MonitoredURLPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    competitor_id: UUID
    url: str
    url_type: URLType
    label: str | None
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


class CompetitorPublic(WithAvatar):
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    website_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    urls: list[MonitoredURLPublic] = []

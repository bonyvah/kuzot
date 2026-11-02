from typing import Literal

from pydantic import BaseModel, Field

from app.models.monitored_url import URLType


class ChannelHint(BaseModel):
    url_type: URLType
    # a handle (@acme) or URL; empty means "please look for one"
    value: str = Field(default="", max_length=2048)
    label: str | None = Field(default=None, max_length=100)


class DiscoverRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: str | None = Field(default=None, max_length=2048)
    description: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    hints: list[ChannelHint] = Field(default=[], max_length=20)


class FindPageRequest(BaseModel):
    looking_for: str = Field(min_length=1, max_length=500)


class DiscoveredPage(BaseModel):
    url: str
    url_type: URLType
    label: str | None
    reason: str
    source: Literal["site", "hint", "search"]


class DiscoverResponse(BaseModel):
    pages: list[DiscoveredPage]
    # things the user should know, e.g. that web search is off
    notes: list[str]
    search_enabled: bool

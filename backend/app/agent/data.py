"""Where the agent's tools read from, always inside one workspace.

The workspace is fixed when the context is built, by code that already checked
access. Tool arguments can only narrow it, so nothing a model or an MCP client
sends can reach another tenant's data.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.monitored_url import MonitoredURL
from app.models.workspace import Workspace
from app.rag.search import Hit, SearchFilters, search


@dataclass(frozen=True)
class InsightQuery:
    competitor_ids: list[str] | None = None
    url_types: list[str] | None = None
    since: datetime | None = None
    # the "now monitoring" markers aren't changes, but they do bound a page's history
    include_started: bool = False
    limit: int = 200


class CompetitorData(Protocol):
    async def search(
        self, query: str, filters: SearchFilters, top_k: int
    ) -> list[Hit]: ...

    async def insights(self, query: InsightQuery) -> list[dict]:
        """Newest first."""
        ...

    async def current_pricing_chunks(self, competitor_ids: list[str]) -> list[dict]: ...


@dataclass(frozen=True)
class ToolContext:
    org_id: str
    workspace_id: str
    competitors: dict[str, str]  # id -> name
    data: CompetitorData
    # chunks of a deleted page stay in Mongo; this says which pages still exist
    monitored_url_ids: frozenset[str] = field(default_factory=frozenset)


class MongoCompetitorData:
    def __init__(self, mongo: AsyncIOMotorDatabase, org_id: str, workspace_id: str):
        self._mongo = mongo
        self._org_id = org_id
        self._workspace_id = workspace_id

    async def search(self, query: str, filters: SearchFilters, top_k: int) -> list[Hit]:
        # OpenAI + Pinecone clients are blocking: keep them off the event loop
        return await asyncio.to_thread(search, query, self._org_id, filters, top_k)

    async def insights(self, query: InsightQuery) -> list[dict]:
        match: dict = {"workspace_id": self._workspace_id}
        if query.competitor_ids:
            match["competitor_id"] = {"$in": query.competitor_ids}
        if query.url_types:
            match["url_type"] = {"$in": query.url_types}
        if query.since:
            match["detected_at"] = {"$gte": query.since}
        if not query.include_started:
            match["kind"] = {"$ne": "monitoring_started"}
        cursor = (
            self._mongo.insights.find(match)
            .sort([("detected_at", -1), ("_id", -1)])
            .limit(query.limit)
        )
        return [doc async for doc in cursor]

    async def current_pricing_chunks(self, competitor_ids: list[str]) -> list[dict]:
        cursor = self._mongo.page_chunks.find(
            {
                "workspace_id": self._workspace_id,
                "competitor_id": {"$in": competitor_ids},
                "url_type": "pricing",
                "removed_at": None,
            },
            {"embedding": 0},
        ).sort([("monitored_url_id", 1), ("first_seen_at", 1)])
        return [doc async for doc in cursor]


async def load_context(
    db: AsyncSession, mongo: AsyncIOMotorDatabase, workspace: Workspace
) -> ToolContext:
    """Build the tool context for a workspace the caller may already read."""
    competitors = await db.execute(
        select(Competitor.id, Competitor.name).where(
            Competitor.workspace_id == workspace.id
        )
    )
    urls = await db.execute(
        select(MonitoredURL.id)
        .join(Competitor, Competitor.id == MonitoredURL.competitor_id)
        .where(Competitor.workspace_id == workspace.id)
    )
    org_id, workspace_id = str(workspace.org_id), str(workspace.id)
    return ToolContext(
        org_id=org_id,
        workspace_id=workspace_id,
        competitors={str(id_): name for id_, name in competitors.all()},
        data=MongoCompetitorData(mongo, org_id, workspace_id),
        monitored_url_ids=frozenset(str(id_) for (id_,) in urls.all()),
    )

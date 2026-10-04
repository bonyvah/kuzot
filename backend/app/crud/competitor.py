from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competitor import Competitor
from app.models.monitored_url import MonitoredURL
from app.schemas.competitor import CompetitorCreate, CompetitorUpdate, MonitoredURLCreate


class CompetitorCRUD:
    async def get_by_id(self, db: AsyncSession, competitor_id: UUID) -> Competitor | None:
        result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self, db: AsyncSession, workspace_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Competitor], int]:
        total_result = await db.execute(
            select(func.count()).select_from(Competitor).where(Competitor.workspace_id == workspace_id)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(Competitor)
            .where(Competitor.workspace_id == workspace_id)
            .order_by(Competitor.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(
        self, db: AsyncSession, workspace_id: UUID, obj_in: CompetitorCreate
    ) -> Competitor:
        competitor = Competitor(
            workspace_id=workspace_id,
            name=obj_in.name,
            description=obj_in.description,
            website_url=obj_in.website_url,
            is_active=True,
        )
        db.add(competitor)
        await db.flush()

        for url_in in obj_in.initial_urls:
            monitored_url = MonitoredURL(
                competitor_id=competitor.id,
                url=url_in.url,
                url_type=url_in.url_type,
                scrape_interval_minutes=url_in.scrape_interval_minutes,
                is_active=True,
            )
            db.add(monitored_url)

        await db.commit()
        await db.refresh(competitor)
        return competitor

    async def update(
        self, db: AsyncSession, competitor: Competitor, obj_in: CompetitorUpdate
    ) -> Competitor:
        if obj_in.name is not None:
            competitor.name = obj_in.name
        if obj_in.description is not None:
            competitor.description = obj_in.description
        if obj_in.website_url is not None:
            competitor.website_url = obj_in.website_url
        if obj_in.is_active is not None:
            competitor.is_active = obj_in.is_active
        await db.commit()
        await db.refresh(competitor)
        return competitor

    async def delete(self, db: AsyncSession, competitor: Competitor) -> None:
        await db.delete(competitor)
        await db.commit()


competitor_crud = CompetitorCRUD()

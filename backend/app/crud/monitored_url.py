from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitored_url import MonitoredURL
from app.schemas.competitor import MonitoredURLCreate, MonitoredURLUpdate, _check_label


class MonitoredURLCRUD:
    async def get_by_id(self, db: AsyncSession, url_id: UUID) -> MonitoredURL | None:
        result = await db.execute(select(MonitoredURL).where(MonitoredURL.id == url_id))
        return result.scalar_one_or_none()

    async def list_by_competitor(
        self, db: AsyncSession, competitor_id: UUID
    ) -> list[MonitoredURL]:
        result = await db.execute(
            select(MonitoredURL)
            .where(MonitoredURL.competitor_id == competitor_id)
            .order_by(MonitoredURL.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self, db: AsyncSession, competitor_id: UUID, obj_in: MonitoredURLCreate
    ) -> MonitoredURL:
        monitored_url = MonitoredURL(
            competitor_id=competitor_id,
            url=obj_in.url,
            url_type=obj_in.url_type,
            label=obj_in.label,
            scrape_interval_minutes=obj_in.scrape_interval_minutes,
            is_active=True,
        )
        db.add(monitored_url)
        await db.commit()
        await db.refresh(monitored_url)
        return monitored_url
    
    async def update(
        self,
        db: AsyncSession,
        monitored_url: MonitoredURL,
        obj_in: MonitoredURLUpdate,
    ) -> MonitoredURL:
        """Apply only the fields the client sent (null interval = manual only)."""
        sent = obj_in.model_fields_set
        if "scrape_interval_minutes" in sent:
            monitored_url.scrape_interval_minutes = obj_in.scrape_interval_minutes
        if obj_in.is_active is not None:
            monitored_url.is_active = obj_in.is_active
        if obj_in.url_type is not None or "label" in sent:
            url_type = obj_in.url_type or monitored_url.url_type
            monitored_url.url_type = url_type
            monitored_url.label = _check_label(
                url_type, obj_in.label if "label" in sent else monitored_url.label
            )
        await db.commit()
        await db.refresh(monitored_url)
        return monitored_url
    
    async def delete(self, db: AsyncSession, monitored_url: MonitoredURL) -> None:
        await db.delete(monitored_url)
        await db.commit()


monitored_url_crud = MonitoredURLCRUD()

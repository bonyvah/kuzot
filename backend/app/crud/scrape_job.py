from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_job import ScrapeJob, ScrapeJobStatus, TriggeredBy
from app.schemas.scrape_job import ScrapeJobCreate


class ScrapeJobCRUD:
    async def get_by_id(self, db: AsyncSession, job_id: UUID) -> ScrapeJob | None:
        result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
        return result.scalar_one_or_none()

    async def list_by_url(
        self, db: AsyncSession, url_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[ScrapeJob], int]:
        total_result = await db.execute(
            select(func.count()).select_from(ScrapeJob).where(ScrapeJob.monitored_url_id == url_id)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(ScrapeJob)
            .where(ScrapeJob.monitored_url_id == url_id)
            .order_by(ScrapeJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, db: AsyncSession, obj_in: ScrapeJobCreate) -> ScrapeJob:
        job = ScrapeJob(
            monitored_url_id=obj_in.monitored_url_id,
            status=ScrapeJobStatus.PENDING,
            triggered_by=obj_in.triggered_by,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job


scrape_job_crud = ScrapeJobCRUD()
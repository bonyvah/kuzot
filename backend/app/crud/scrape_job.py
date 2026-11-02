from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitored_url import MonitoredURL
from app.models.scrape_job import (
    ACTIVE_JOB_WINDOW,
    ScrapeJob,
    ScrapeJobStatus,
    TriggeredBy,
)
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

    async def lock_url_and_get_active(
        self, db: AsyncSession, url_id: UUID
    ) -> ScrapeJob | None:
        """Lock the URL row, then return its in-flight job if it has one.

        The row lock lasts until the caller commits (create() does) or the
        session ends, so two concurrent triggers can't both see "no active job".
        """
        await db.execute(
            select(MonitoredURL.id).where(MonitoredURL.id == url_id).with_for_update()
        )
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - ACTIVE_JOB_WINDOW
        result = await db.execute(
            select(ScrapeJob)
            .where(
                ScrapeJob.monitored_url_id == url_id,
                ScrapeJob.status.in_(
                    [ScrapeJobStatus.PENDING, ScrapeJobStatus.RUNNING]
                ),
                ScrapeJob.created_at > cutoff,
            )
            .order_by(ScrapeJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

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

    async def mark_failed(
        self, db: AsyncSession, job: ScrapeJob, message: str
    ) -> ScrapeJob:
        job.status = ScrapeJobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        job.error_message = message[:1000]
        await db.commit()
        await db.refresh(job)
        return job


scrape_job_crud = ScrapeJobCRUD()
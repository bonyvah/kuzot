from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.models.scrape_job import ScrapeJobStatus, TriggeredBy


class ScrapeJobCreate(BaseModel):
    monitored_url_id: UUID
    triggered_by: TriggeredBy = TriggeredBy.MANUAL


class ScrapeJobPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monitored_url_id: UUID
    celery_task_id: str | None
    status: ScrapeJobStatus
    triggered_by: TriggeredBy
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    content_changed: bool | None
    mongo_snapshot_id: str | None
    created_at: datetime
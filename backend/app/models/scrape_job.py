import uuid
import enum
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class ScrapeJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TriggeredBy(enum.StrEnum):
    SCHEDULER = "scheduler"
    MANUAL = "manual"


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    monitored_url_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("monitored_urls.id", ondelete="CASCADE"), index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[ScrapeJobStatus] = mapped_column(
        Enum(ScrapeJobStatus, native_enum=False), default=ScrapeJobStatus.PENDING
    )
    triggered_by: Mapped[TriggeredBy] = mapped_column(
        Enum(TriggeredBy, native_enum=False)
    )
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    content_changed: Mapped[bool | None]
    mongo_snapshot_id: Mapped[str | None] = mapped_column(String(24))
    # MongoDB ObjectId = 24 hex chars

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

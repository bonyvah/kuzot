import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base

if TYPE_CHECKING:
    from app.models.competitor import Competitor


class URLType(enum.StrEnum):
    HOMEPAGE = "homepage"
    PRICING = "pricing"
    BLOG = "blog"
    DOCS = "docs"
    CHANGELOG = "changelog"


class MonitoredURL(Base):
    __tablename__ = "monitored_urls"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("competitors.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    url_type: Mapped[URLType] = mapped_column(SAEnum(URLType, native_enum=False))
    scrape_interval_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    last_scraped_at: Mapped[datetime | None]
    last_content_hash: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    competitor: Mapped["Competitor"] = relationship(
        back_populates="urls",
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "ix_monitored_urls_polling",
            "is_active",
            "scrape_interval_minutes",
            "last_scraped_at",
        ),
    )

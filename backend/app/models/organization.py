import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base

if TYPE_CHECKING:
    from app.models.org_member import OrgMember
    from app.models.workspace import Workspace


class OrgType(enum.StrEnum):
    PERSONAL = "personal"
    TEAM = "team"


class OrgPlan(enum.StrEnum):
    FREE = "free"
    INDIVIDUAL = "individual"
    TEAM = "team"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    org_type: Mapped[OrgType] = mapped_column(
        SAEnum(OrgType, native_enum=False),
        default=OrgType.PERSONAL,
    )
    plan: Mapped[OrgPlan] = mapped_column(
        SAEnum(OrgPlan, native_enum=False),
        default=OrgPlan.FREE,
    )
    # SET NULL so deleting the creator doesn't cascade-delete the whole org
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )

    # selectin: always want members when loading an org (small list)
    members: Mapped[list["OrgMember"]] = relationship(
        back_populates="organization",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    # raise: workspace list can be large — load explicitly with selectinload()
    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="organization",
        lazy="raise",
        cascade="all, delete-orphan",
    )

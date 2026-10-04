import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class MemberRole(enum.StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class OrgMember(Base):
    __tablename__ = "org_members"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[MemberRole] = mapped_column(
        SAEnum(MemberRole, native_enum=False),
        default=MemberRole.MEMBER,
    )
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # joined: both are single records — cheap to always load via JOIN
    organization: Mapped["Organization"] = relationship(
        back_populates="members",
        lazy="joined",
    )
    user: Mapped["User"] = relationship(lazy="joined")

    __table_args__ = (
        # Prevents duplicate membership rows at the DB level
        UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),
    )

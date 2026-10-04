from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org_member import MemberRole, OrgMember


class OrgMemberCRUD:
    async def get_by_user_and_org(
        self, db: AsyncSession, user_id: UUID, org_id: UUID
    ) -> OrgMember | None:
        result = await db.execute(
            select(OrgMember).where(
                OrgMember.user_id == user_id,
                OrgMember.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self, db: AsyncSession, org_id: UUID
    ) -> list[OrgMember]:
        result = await db.execute(
            select(OrgMember).where(OrgMember.org_id == org_id)
        )
        return list(result.scalars().all())

    async def add_member(
        self, db: AsyncSession, org_id: UUID, user_id: UUID, role: MemberRole
    ) -> OrgMember:
        member = OrgMember(org_id=org_id, user_id=user_id, role=role)
        db.add(member)
        await db.commit()
        await db.refresh(member)
        return member

    async def update_role(
        self, db: AsyncSession, member: OrgMember, new_role: MemberRole
    ) -> OrgMember:
        member.role = new_role
        await db.commit()
        await db.refresh(member)
        return member

    async def remove_member(
        self, db: AsyncSession, member: OrgMember
    ) -> None:
        await db.delete(member)
        await db.commit()


org_member_crud = OrgMemberCRUD()

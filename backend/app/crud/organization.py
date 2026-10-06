import re
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrgPlan, OrgType
from app.models.org_member import MemberRole, OrgMember
from app.models.workspace import Workspace
from app.schemas.organization import OrgCreate, OrgUpdate


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text)


class OrganizationCRUD:
    async def get_by_id(self, db: AsyncSession, org_id: UUID) -> Organization | None:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Organization | None:
        result = await db.execute(select(Organization).where(Organization.slug == slug))
        return result.scalar_one_or_none()

    async def get_user_personal_org(self, db: AsyncSession, user_id: UUID) -> Organization | None:
        result = await db.execute(
            select(Organization)
            .where(
                Organization.created_by_user_id == user_id,
                Organization.org_type == OrgType.PERSONAL,
            )
        )
        return result.scalar_one_or_none()

    async def list_user_orgs(
        self, db: AsyncSession, user_id: UUID
    ) -> list[Organization]:
        result = await db.execute(
            select(Organization)
            .join(OrgMember, OrgMember.org_id == Organization.id)
            .where(OrgMember.user_id == user_id)
            .order_by(Organization.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self, db: AsyncSession, obj_in: OrgCreate, user_id: UUID
    ) -> Organization:
        base_slug = slugify(obj_in.name)
        slug = base_slug
        counter = 1
        while await self.get_by_slug(db, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        org = Organization(
            name=obj_in.name,
            slug=slug,
            org_type=obj_in.org_type,
            plan=OrgPlan.FREE,
            created_by_user_id=user_id,
        )
        db.add(org)
        await db.flush()  # get org.id

        # Creator becomes OWNER
        owner_member = OrgMember(
            org_id=org.id,
            user_id=user_id,
            role=MemberRole.OWNER,
        )
        db.add(owner_member)

        # Automatically create default "General" workspace
        default_workspace = Workspace(
            org_id=org.id,
            name="General",
            description="Default workspace",
            created_by_user_id=user_id,
        )
        db.add(default_workspace)

        await db.commit()
        await db.refresh(org)
        return org

    async def update(
        self, db: AsyncSession, org: Organization, obj_in: OrgUpdate
    ) -> Organization:
        if obj_in.name is not None and obj_in.name != org.name:
            org.name = obj_in.name
            base_slug = slugify(obj_in.name)
            slug = base_slug
            counter = 1
            while True:
                existing = await self.get_by_slug(db, slug)
                if not existing or existing.id == org.id:
                    break
                slug = f"{base_slug}-{counter}"
                counter += 1
            org.slug = slug

        await db.commit()
        await db.refresh(org)
        return org

    async def delete(self, db: AsyncSession, org: Organization) -> None:
        await db.delete(org)
        await db.commit()


organization_crud = OrganizationCRUD()

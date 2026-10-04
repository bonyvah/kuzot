from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceCRUD:
    async def get_by_id(self, db: AsyncSession, workspace_id: UUID) -> Workspace | None:
        result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def list_by_org(
        self, db: AsyncSession, org_id: UUID
    ) -> list[Workspace]:
        result = await db.execute(
            select(Workspace)
            .where(Workspace.org_id == org_id)
            .order_by(Workspace.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self, db: AsyncSession, org_id: UUID, obj_in: WorkspaceCreate, user_id: UUID
    ) -> Workspace:
        workspace = Workspace(
            org_id=org_id,
            name=obj_in.name,
            description=obj_in.description,
            created_by_user_id=user_id,
        )
        db.add(workspace)
        await db.commit()
        await db.refresh(workspace)
        return workspace

    async def update(
        self, db: AsyncSession, workspace: Workspace, obj_in: WorkspaceUpdate
    ) -> Workspace:
        if obj_in.name is not None:
            workspace.name = obj_in.name
        if obj_in.description is not None:
            workspace.description = obj_in.description
        await db.commit()
        await db.refresh(workspace)
        return workspace

    async def delete(self, db: AsyncSession, workspace: Workspace) -> None:
        await db.delete(workspace)
        await db.commit()


workspace_crud = WorkspaceCRUD()

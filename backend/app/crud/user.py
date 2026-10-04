from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserUpdate


class UserCRUD:
    async def get_by_id(self, db: AsyncSession, user_id: UUID) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj_in: RegisterRequest) -> User:
        user = User(
            email=obj_in.email.lower().strip(),
            hashed_password=hash_password(obj_in.password),
            full_name=obj_in.full_name,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def update(self, db: AsyncSession, user: User, obj_in: UserUpdate) -> User:
        if obj_in.full_name is not None:
            user.full_name = obj_in.full_name
        await db.commit()
        await db.refresh(user)
        return user


user_crud = UserCRUD()

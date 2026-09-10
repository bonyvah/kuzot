from collections.abc import AsyncGenerator
from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends, Request
from redis.asyncio import Redis

from app.db.postgres import AsyncSessionLocal
from app.db.mongo import get_mongo_db


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_mongodb() -> AsyncIOMotorDatabase:
    return get_mongo_db()

def get_redis(request: Request) -> Redis:
    return request.app.state.redis

DBSession = Annotated[AsyncSession, Depends(get_db)]
MongoDBDep = Annotated[AsyncIOMotorDatabase, Depends(get_mongodb)]
RedisDep = Annotated[Redis, Depends(get_redis)]
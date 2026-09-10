from redis.asyncio import from_url, Redis
from fastapi import FastAPI

from app.core.config import settings

def _create_redis_client() -> Redis:
    return from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True
    )

def set_redis(app:FastAPI):
    app.state.redis = _create_redis_client()

async def close_redis(app:FastAPI):
    await app.state.redis.aclose()
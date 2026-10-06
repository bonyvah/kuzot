import json
from typing import Any
from redis.asyncio import Redis


async def get_cached_json(redis: Redis, key: str) -> Any | None:
    """Retrieve and deserialize JSON from Redis if key exists."""
    cached = await redis.get(key)
    if cached:
        return json.loads(cached.decode("utf-8"))
    return None


async def set_cached_json(redis: Redis, key: str, data: Any, ttl_seconds: int = 300) -> None:
    """Serialize and store data in Redis with a Time-To-Live (default 5 minutes)."""
    serialized = json.dumps(data, default=str)  
    await redis.setex(key, ttl_seconds, serialized)


async def invalidate_cache_pattern(redis: Redis, pattern: str) -> None:
    """Find and delete all cache keys matching a pattern (e.g. 'competitor:123:*')."""
    keys = await redis.keys(pattern)
    if keys:
        await redis.delete(*keys)
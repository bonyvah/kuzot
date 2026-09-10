from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings


class MongoDB:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongodb = MongoDB()


async def connect_to_mongo() -> None:
    mongodb.client = AsyncIOMotorClient(settings.MONGO_URI)
    mongodb.db = mongodb.client[settings.MONGO_DB_NAME]

    await mongodb.db.page_snapshots.create_index(
        [("monitored_url_id", 1), ("scraped_at", -1)]
    )
    await mongodb.db.page_snapshots.create_index([("content_hash", 1)])
    await mongodb.db.change_events.create_index([("detected_at", -1)])
    await mongodb.db.change_events.create_index([("embedding_status", 1)])


async def close_mongo_connection() -> None:
    if mongodb.client:
        mongodb.client.close()


def get_mongo_db() -> AsyncIOMotorDatabase:
    if mongodb.db is None:
        raise RuntimeError("MongoDB not connected. Did lifespan run?")
    return mongodb.db

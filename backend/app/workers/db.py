from functools import cache

from pymongo import MongoClient
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", "+psycopg"),
    pool_size=10,
    max_overflow=40,
    pool_pre_ping=True,
)
SyncSession = sessionmaker(bind=sync_engine, expire_on_commit=False)

@cache
def get_mongo_db():
    return MongoClient(settings.MONGO_URI)[settings.MONGO_DB_NAME]


@cache
def get_redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL)

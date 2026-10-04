from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── PostgreSQL ──────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_URL_TEST: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/kuzot_test"

    # ── MongoDB ─────────────────────────────────────────────────────
    MONGO_URI: str
    MONGO_DB_NAME: str = "kuzot"

    # ── Redis ───────────────────────────────────────────────────────
    REDIS_URL: str                 # DB 0 — caching + token blacklist
    CELERY_RESULT_BACKEND: str     # DB 1 — Celery task results

    # ── RabbitMQ ────────────────────────────────────────────────────
    RABBITMQ_URL: str

    # ── AI / Vector ─────────────────────────────────────────────────
    OPENAI_API_KEY: str
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str

    # ── Auth (JWT) ──────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── AWS / LocalStack ────────────────────────────────────────────
    AWS_ENDPOINT_URL: str | None = None   # http://localhost:4566 locally, None in prod
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_REPORTS: str = "kuzot-reports"

    # ── App ─────────────────────────────────────────────────────────
    APP_ENV: Literal["dev", "prod", "test"] = "dev"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()  # type: ignore
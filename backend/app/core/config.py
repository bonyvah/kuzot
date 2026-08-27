from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # DATABASE_URL == database_url
        extra="ignore"
    )

    # ── PostgreSQL ──────────────────────────────────
    DATABASE_URL: str
    DATABASE_URL_TEST: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/kuzot_test"

    # ── MongoDB ─────────────────────────────────────
    MONGO_URI: str
    MONGO_DB_NAME: str = "kuzot"

    # ── Redis ───────────────────────────────────────
    REDIS_URL: str                    # DB 0 — caching
    CELERY_RESULT_BACKEND: str        # DB 1 — task results

    # ── RabbitMQ ─────────────────────────────────────
    RABBITMQ_URL: str

    # ── AI / Vector ──────────────────────────────────
    OPENAI_API_KEY: str
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str

    # ── Auth ─────────────────────────────────────────
    API_SECRET_KEY: str

    # ── App ──────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = False


settings = Settings() # type: ignore
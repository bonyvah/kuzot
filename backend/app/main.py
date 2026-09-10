from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from fastapi.responses import JSONResponse

from app.db.mongo import connect_to_mongo, close_mongo_connection
from app.db.dependencies import DBSession
from app.db.redis import set_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    set_redis(app)

    yield

    await close_mongo_connection()
    await close_redis(app)


app = FastAPI(
    title="Kuzot CI Platform",
    version="0.1.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(api_router, prefix="/api/v1")


@app.get("/health/live")
async def liveness():
    return {"status":"ok"}

@app.get("/health/ready")
async def readiness(db:DBSession):
    try:
        await db.execute(text("SELECT 1"))
        return {"status":"ok", "db":"connected"}
    except Exception:  # noqa: BLE001
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status":"error", "db":"unavailable"}
        )
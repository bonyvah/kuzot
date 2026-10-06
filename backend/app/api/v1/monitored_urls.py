import math
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis

from app.core.auth_dependencies import CurrentUser, require_org_role
from app.core.cache import get_cached_json, set_cached_json, invalidate_cache_pattern
from app.core.exceptions import CompetitorNotFoundError, MonitoredURLNotFoundError
from app.crud.competitor import competitor_crud
from app.crud.monitored_url import monitored_url_crud
from app.crud.scrape_job import scrape_job_crud
from app.crud.workspace import workspace_crud
from app.db.dependencies import DBSession
from app.db.redis import get_redis
from app.models.org_member import MemberRole
from app.models.scrape_job import TriggeredBy
from app.schemas.common import PaginatedResponse
from app.schemas.competitor import MonitoredURLPublic
from app.schemas.scrape_job import ScrapeJobCreate, ScrapeJobPublic

router = APIRouter(tags=["Monitored URLs & Scraping"])


@router.get(
    "/competitors/{competitor_id}/urls",
    response_model=list[MonitoredURLPublic],
)
async def list_competitor_urls(
    competitor_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
):
    competitor = await competitor_crud.get_by_id(db, competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(competitor_id))

    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    cache_key = f"competitor:{competitor_id}:urls"

    # 1. Check Redis cache first
    cached_data = await get_cached_json(redis, cache_key)
    if cached_data is not None:
        return cached_data

    # 2. Query DB on cache miss
    urls = await monitored_url_crud.list_by_competitor(db, competitor_id)

    # 3. Store in Redis cache for 5 minutes
    serialized_urls = [MonitoredURLPublic.model_validate(u).model_dump(mode="json") for u in urls]
    await set_cached_json(redis, cache_key, serialized_urls, ttl_seconds=300)

    return urls


@router.patch("/monitored-urls/{url_id}", response_model=MonitoredURLPublic)
async def update_monitored_url(
    url_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
    scrape_interval_minutes: int | None = None,
    is_active: bool | None = None,
):
    url_record = await monitored_url_crud.get_by_id(db, url_id)
    if not url_record:
        raise MonitoredURLNotFoundError(str(url_id))

    competitor = await competitor_crud.get_by_id(db, url_record.competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(url_record.competitor_id))

    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    updated_url = await monitored_url_crud.update(
        db, url_record, scrape_interval_minutes=scrape_interval_minutes, is_active=is_active
    )

    await invalidate_cache_pattern(redis, f"competitor:{competitor.id}:urls")

    return updated_url


@router.post(
    "/monitored-urls/{url_id}/trigger",
    response_model=ScrapeJobPublic,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_manual_scrape(
    url_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    url_record = await monitored_url_crud.get_by_id(db, url_id)
    if not url_record:
        raise MonitoredURLNotFoundError(str(url_id))

    competitor = await competitor_crud.get_by_id(db, url_record.competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(url_record.competitor_id))

    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    job = await scrape_job_crud.create(
        db,
        obj_in=ScrapeJobCreate(monitored_url_id=url_id, triggered_by=TriggeredBy.MANUAL),
    )

    return job


@router.get(
    "/monitored-urls/{url_id}/jobs",
    response_model=PaginatedResponse[ScrapeJobPublic],
)
async def list_url_scrape_jobs(
    url_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    url_record = await monitored_url_crud.get_by_id(db, url_id)
    if not url_record:
        raise MonitoredURLNotFoundError(str(url_id))

    competitor = await competitor_crud.get_by_id(db, url_record.competitor_id)
    if not competitor:
        raise CompetitorNotFoundError(str(url_record.competitor_id))

    workspace = await workspace_crud.get_by_id(db, competitor.workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    await require_org_role(current_user, workspace.org_id, MemberRole.MEMBER, db)

    skip = (page - 1) * size
    jobs, total = await scrape_job_crud.list_by_url(db, url_id=url_id, skip=skip, limit=size)
    pages = math.ceil(total / size) if total > 0 else 1

    # Convert SQLAlchemy ORM models to Pydantic models for Pylance type safety
    job_items = [ScrapeJobPublic.model_validate(job) for job in jobs]

    return PaginatedResponse[ScrapeJobPublic](
        items=job_items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
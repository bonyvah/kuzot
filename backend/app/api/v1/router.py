from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.workspaces import router as workspaces_router
from app.api.v1.competitors import router as competitors_router
from app.api.v1.monitored_urls import router as monitored_urls_router
from app.api.v1.intelligence import router as intelligence_router
from app.api.v1.insights import router as insights_router
from app.api.v1.discovery import router as discovery_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(workspaces_router)
api_router.include_router(competitors_router)
api_router.include_router(monitored_urls_router)
api_router.include_router(intelligence_router)
api_router.include_router(insights_router)
api_router.include_router(discovery_router)

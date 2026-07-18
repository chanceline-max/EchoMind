"""Version 1 API router."""

from fastapi import APIRouter

from echomind.api.v1.analysis import router as analysis_router
from echomind.api.v1.conversations import router as conversations_router
from echomind.api.v1.health import router as health_router
from echomind.api.v1.imports import router as imports_router
from echomind.api.v1.insights import router as insights_router
from echomind.api.v1.messages import router as messages_router
from echomind.api.v1.profiles import router as profiles_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(analysis_router)
api_router.include_router(imports_router)
api_router.include_router(conversations_router)
api_router.include_router(messages_router)
api_router.include_router(insights_router)
api_router.include_router(profiles_router)

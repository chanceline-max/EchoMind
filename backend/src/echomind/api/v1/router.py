"""Version 1 API router."""

from fastapi import APIRouter

from echomind.api.v1.conversations import router as conversations_router
from echomind.api.v1.health import router as health_router
from echomind.api.v1.imports import router as imports_router
from echomind.api.v1.messages import router as messages_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(imports_router)
api_router.include_router(conversations_router)
api_router.include_router(messages_router)

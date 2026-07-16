"""Health check endpoint and response contract."""

from typing import Literal, cast

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, ConfigDict

from echomind.core.config import Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Public health response with no configuration details."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def read_health(request: Request, response: Response) -> HealthResponse:
    """Report API availability without exposing environment configuration."""
    settings = cast(Settings, request.app.state.settings)
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse(
        status="ok",
        service="echomind-api",
        version=settings.app_version,
    )

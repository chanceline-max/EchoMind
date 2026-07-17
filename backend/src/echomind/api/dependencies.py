"""FastAPI dependencies for database sessions and local write protection."""

from collections.abc import Iterator
from typing import cast

from fastapi import Request, Response
from sqlalchemy.orm import Session, sessionmaker

from echomind.api.errors import ApiError
from echomind.core.config import Settings


def get_db_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


def require_allowed_origin(request: Request) -> None:
    """Reject browser write requests from origins outside the exact allowlist."""

    origin = request.headers.get("origin")
    if origin is None:
        return
    settings = cast(Settings, request.app.state.settings)
    if origin not in settings.frontend_origins:
        raise ApiError(
            "origin_not_allowed",
            status_code=403,
            message="This origin is not allowed to modify local EchoMind data.",
        )


def set_private_response_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

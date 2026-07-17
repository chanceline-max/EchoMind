"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from echomind.api.errors import ApiError, api_error_handler, validation_error_handler
from echomind.api.middleware import ImportRequestGuardMiddleware
from echomind.api.v1.router import api_router
from echomind.core.config import Settings, get_settings
from echomind.db.session import create_db_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application using explicit settings when supplied by tests."""
    app_settings = settings or get_settings()
    engine = create_db_engine(app_settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.add_exception_handler(ApiError, cast(Any, api_error_handler))
    application.add_exception_handler(
        RequestValidationError,
        cast(Any, validation_error_handler),
    )
    application.add_middleware(
        ImportRequestGuardMiddleware,
        import_path=f"{app_settings.api_v1_prefix}/imports",
        allowed_origins=app_settings.frontend_origins,
        max_content_length=app_settings.import_max_file_bytes + 1_048_576,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Accept", "Content-Type"],
    )
    application.include_router(api_router, prefix=app_settings.api_v1_prefix)
    return application


app = create_app()

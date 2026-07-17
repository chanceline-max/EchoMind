"""Guards that must run before multipart body parsing."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from echomind.api.errors import ErrorResponse


class ImportRequestGuardMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        import_path: str,
        allowed_origins: list[str],
        max_content_length: int,
    ) -> None:
        super().__init__(app)
        self.import_path = import_path
        self.allowed_origins = frozenset(allowed_origins)
        self.max_content_length = max_content_length

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method == "POST" and request.url.path == self.import_path:
            origin = request.headers.get("origin")
            if origin is not None and origin not in self.allowed_origins:
                return self._error(
                    403,
                    ErrorResponse(
                        error_code="origin_not_allowed",
                        message="This origin is not allowed to modify local EchoMind data.",
                    ),
                )
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    too_large = int(content_length) > self.max_content_length
                except ValueError:
                    too_large = False
                if too_large:
                    return self._error(
                        413,
                        ErrorResponse(
                            error_code="upload_too_large",
                            message="The uploaded file exceeds the configured size limit.",
                        ),
                    )
        return await call_next(request)

    @staticmethod
    def _error(status_code: int, error: ErrorResponse) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=error.model_dump(mode="json", exclude_none=True),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

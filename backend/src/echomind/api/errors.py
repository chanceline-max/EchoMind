"""Safe API error contract shared by stage-five endpoints."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    recoverable: bool = False
    safe_filename: str | None = None
    location: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ApiError(Exception):
    """Expected failure whose fields are safe to return to a local client."""

    def __init__(
        self,
        error_code: str,
        *,
        status_code: int,
        message: str,
        recoverable: bool = False,
        safe_filename: str | None = None,
        location: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.payload = ErrorResponse(
            error_code=error_code,
            message=message,
            recoverable=recoverable,
            safe_filename=safe_filename,
            location=location,
            details=details or {},
        )
        super().__init__(message)


def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=error.status_code,
        content=error.payload.model_dump(mode="json", exclude_none=True),
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    del request
    locations = [
        [str(part) for part in item.get("loc", ()) if part not in {"body", "file"}]
        for item in error.errors()
    ]
    payload = ErrorResponse(
        error_code="invalid_request",
        message="The request fields are not valid.",
        details={"locations": locations[:20]},
    )
    return JSONResponse(
        status_code=422,
        content=payload.model_dump(mode="json", exclude_none=True),
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )

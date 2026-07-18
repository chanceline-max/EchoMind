"""Safe failures raised by Profile selection, rendering, and persistence."""

from typing import Any


class ProfileError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 422,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.recoverable = recoverable
        self.details = details or {}
        super().__init__(message)

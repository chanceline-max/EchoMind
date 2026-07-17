"""Safe structured failures for the in-memory cleaning pipeline."""

from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


class CleaningErrorCode(StrEnum):
    INVALID_CONFIGURATION = "invalid_configuration"
    INTERNAL_CLEANER_ERROR = "internal_cleaner_error"
    INVALID_CLEANED_RESULT = "invalid_cleaned_result"


def safe_display_name(value: str | object) -> str:
    """Return a cross-platform basename without exposing a local path."""

    raw = str(value).replace("\x00", "").strip()
    return PureWindowsPath(PurePosixPath(raw).name).name or "unknown-file"


_SAFE_DETAIL_KEYS = frozenset({"exception_type", "field", "reason"})


def _safe_details(details: dict[str, Any] | None) -> dict[str, str | int | bool]:
    if not details:
        return {}
    safe: dict[str, str | int | bool] = {}
    for key, value in details.items():
        if key not in _SAFE_DETAIL_KEYS or not isinstance(value, (str, int, bool)):
            continue
        rendered = str(value)
        if any(marker in rendered for marker in ("/", "\\", "\n", "\r")):
            continue
        safe[key] = value
    return safe


class CleaningError(Exception):
    """A pipeline failure containing only safe identifiers and structural context."""

    def __init__(
        self,
        error_code: CleaningErrorCode | str,
        *,
        safe_filename: str,
        cleaner_name: str | None,
        message: str,
        conversation_source_id: str | None = None,
        message_source_id: str | None = None,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = CleaningErrorCode(error_code)
        self.safe_filename = safe_display_name(safe_filename)
        self.cleaner_name = cleaner_name
        self.message = message
        self.conversation_source_id = conversation_source_id
        self.message_source_id = message_source_id
        self.recoverable = recoverable
        self.details = _safe_details(details)
        super().__init__(self.__str__())

    def __str__(self) -> str:
        cleaner = f" [{self.cleaner_name}]" if self.cleaner_name else ""
        return f"[{self.error_code}]{cleaner} {self.message} ({self.safe_filename})"

    def as_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "safe_filename": self.safe_filename,
            "cleaner_name": self.cleaner_name,
            "message": self.message,
            "conversation_source_id": self.conversation_source_id,
            "message_source_id": self.message_source_id,
            "recoverable": self.recoverable,
            "details": self.details,
        }

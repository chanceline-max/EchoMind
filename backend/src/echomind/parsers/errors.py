"""Safe structured Parser errors."""

from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


class ErrorCode(StrEnum):
    AMBIGUOUS_FORMAT = "ambiguous_format"
    DUPLICATE_CONVERSATION = "duplicate_conversation"
    DUPLICATE_MESSAGE = "duplicate_message"
    DUPLICATE_PARTICIPANT = "duplicate_participant"
    ENCODING_ERROR = "encoding_error"
    FILE_READ_ERROR = "file_read_error"
    INTERNAL_PARSER_ERROR = "internal_parser_error"
    INVALID_BOOLEAN = "invalid_boolean"
    INVALID_FORMAT = "invalid_format"
    INVALID_HEADERS = "invalid_headers"
    INVALID_JSON = "invalid_json"
    INVALID_RECORD = "invalid_record"
    INVALID_STRUCTURE = "invalid_structure"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_TIME_RANGE = "invalid_time_range"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    MISSING_TIMEZONE = "missing_timezone"
    MULTIPLE_PROFILE_OWNERS = "multiple_profile_owners"
    NO_VALID_CONVERSATIONS = "no_valid_conversations"
    NO_VALID_MESSAGES = "no_valid_messages"
    PARTICIPANT_CONFLICT = "participant_conflict"
    SAMPLE_REQUIRED = "sample_required"
    STATISTICS_MISMATCH = "statistics_mismatch"
    UNKNOWN_PARSER = "unknown_parser"
    UNKNOWN_REPLY = "unknown_reply"
    UNKNOWN_SENDER = "unknown_sender"
    UNSUPPORTED_EXTENSION = "unsupported_extension"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNSUPPORTED_MESSAGE_TYPE = "unsupported_message_type"
    UNSUPPORTED_VERSION = "unsupported_version"


def safe_display_name(value: str | object) -> str:
    """Return only a cross-platform basename suitable for errors and output."""

    raw = str(value).replace("\x00", "").strip()
    posix_name = PurePosixPath(raw).name
    windows_name = PureWindowsPath(posix_name).name
    return windows_name or "unknown-file"


class ParserError(Exception):
    """An expected Parser failure that never embeds source content or full paths."""

    def __init__(
        self,
        error_code: ErrorCode | str,
        *,
        safe_filename: str,
        message: str,
        parser_name: str | None = None,
        location: str | None = None,
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = ErrorCode(error_code)
        self.safe_filename = safe_display_name(safe_filename)
        self.message = message
        self.parser_name = parser_name
        self.location = location
        self.recoverable = recoverable
        self.details = details or {}
        super().__init__(self.__str__())

    def __str__(self) -> str:
        location = f" at {self.location}" if self.location else ""
        return f"[{self.error_code}] {self.message} ({self.safe_filename}){location}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "safe_filename": self.safe_filename,
            "message": self.message,
            "parser_name": self.parser_name,
            "location": self.location,
            "recoverable": self.recoverable,
            "details": self.details,
        }

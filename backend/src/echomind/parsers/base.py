"""Parser protocol and shared safe I/O helpers."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from echomind.parsers.errors import ErrorCode, ParserError, safe_display_name
from echomind.parsers.options import ErrorMode, ParserOptions
from echomind.parsers.schemas import ParsedChatFile, ParseWarning

SIGNATURE_READ_SIZE = 8192


class ChatParser(Protocol):
    parser_name: str
    parser_version: str
    supported_extensions: frozenset[str]
    available: bool

    def can_parse(self, path: Path) -> bool: ...

    def parse(self, path: Path, options: ParserOptions | None = None) -> ParsedChatFile: ...

    def validate(self, result: ParsedChatFile) -> ParsedChatFile: ...


@dataclass
class ParseState:
    """Mutable per-parse counters; never contains chat content."""

    options: ParserOptions
    warnings: list[ParseWarning] = field(default_factory=list)
    skipped_record_count: int = 0

    def reject_record(self, error: ParserError) -> None:
        if self.options.error_mode is ErrorMode.STRICT or not error.recoverable:
            raise error
        self.warnings.append(
            ParseWarning(
                error_code=error.error_code,
                message=error.message,
                location=error.location,
                recoverable=True,
                details=error.details,
            )
        )
        self.skipped_record_count += 1


def read_source_text(path: Path, options: ParserOptions, parser_name: str) -> str:
    """Decode source bytes explicitly without encoding detection."""

    safe_filename = safe_display_name(path)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ParserError(
            ErrorCode.FILE_READ_ERROR,
            safe_filename=safe_filename,
            parser_name=parser_name,
            message="The source file could not be read.",
            recoverable=False,
            details={"reason": type(error).__name__},
        ) from None

    encoding = "utf-8-sig" if options.encoding in {"utf-8", "utf-8-sig"} else options.encoding
    try:
        return raw.decode(encoding)
    except UnicodeError as error:
        raise ParserError(
            ErrorCode.ENCODING_ERROR,
            safe_filename=safe_filename,
            parser_name=parser_name,
            message="The source file is not valid in the selected encoding.",
            recoverable=False,
            details={"encoding": options.encoding, "reason": type(error).__name__},
        ) from None


def read_signature(path: Path) -> bytes:
    """Read only a small prefix for lightweight format recognition."""

    try:
        with path.open("rb") as source:
            return source.read(SIGNATURE_READ_SIZE)
    except OSError:
        return b""


def validation_fields(error: ValidationError) -> list[str]:
    """Extract field locations without including rejected input values."""

    return sorted({".".join(str(item) for item in entry["loc"]) for entry in error.errors()})


def require_fields(
    data: dict[str, object],
    fields: Iterable[str],
    *,
    safe_filename: str,
    parser_name: str,
    location: str,
    recoverable: bool,
) -> None:
    missing = sorted(field for field in fields if field not in data)
    if missing:
        raise ParserError(
            ErrorCode.MISSING_REQUIRED_FIELD,
            safe_filename=safe_filename,
            parser_name=parser_name,
            message="A required field is missing from the record.",
            location=location,
            recoverable=recoverable,
            details={"fields": missing},
        )


def reject_unknown_fields(
    data: dict[str, object],
    allowed: set[str],
    *,
    safe_filename: str,
    parser_name: str,
    location: str,
    recoverable: bool,
) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ParserError(
            ErrorCode.INVALID_STRUCTURE,
            safe_filename=safe_filename,
            parser_name=parser_name,
            message="The record contains unsupported fields.",
            location=location,
            recoverable=recoverable,
            details={"fields": unknown},
        )

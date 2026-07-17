"""Streaming SHA-256 over untouched source bytes."""

import hashlib
from pathlib import Path

from echomind.parsers.errors import ErrorCode, ParserError, safe_display_name

DEFAULT_CHUNK_SIZE = 64 * 1024


def hash_file(path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Hash the exact source bytes without reading the whole file at once."""

    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while chunk := source.read(chunk_size):
                digest.update(chunk)
    except OSError as error:
        raise ParserError(
            ErrorCode.FILE_READ_ERROR,
            safe_filename=safe_display_name(path),
            message="The source file could not be read.",
            recoverable=False,
            details={"reason": type(error).__name__},
        ) from None
    return digest.hexdigest()

"""Explicitly unsupported WeFlow adapter boundary."""

from pathlib import Path

from echomind.parsers.errors import ErrorCode, ParserError, safe_display_name
from echomind.parsers.options import ParserOptions
from echomind.parsers.schemas import ParsedChatFile


class WeFlowParser:
    parser_name = "weflow"
    parser_version = "0.0"
    supported_extensions: frozenset[str] = frozenset({".json"})
    available = False

    def can_parse(self, path: Path) -> bool:
        del path
        return False

    def parse(self, path: Path, options: ParserOptions | None = None) -> ParsedChatFile:
        del options
        raise ParserError(
            ErrorCode.SAMPLE_REQUIRED,
            safe_filename=safe_display_name(path),
            parser_name=self.parser_name,
            message="WeFlow parsing requires an authorized and fully anonymized format sample.",
            recoverable=False,
        )

    def validate(self, result: ParsedChatFile) -> ParsedChatFile:
        raise ParserError(
            ErrorCode.SAMPLE_REQUIRED,
            safe_filename=result.source_filename,
            parser_name=self.parser_name,
            message="WeFlow parsing is not implemented without an authorized sample.",
            recoverable=False,
        )

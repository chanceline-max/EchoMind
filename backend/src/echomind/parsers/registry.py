"""Deterministic in-repository Parser Registry."""

from collections.abc import Iterable
from pathlib import Path

from echomind.parsers.base import ChatParser
from echomind.parsers.csv_parser import GenericCsvParser
from echomind.parsers.errors import ErrorCode, ParserError, safe_display_name
from echomind.parsers.json_parser import GenericJsonParser
from echomind.parsers.options import ParserOptions
from echomind.parsers.schemas import CanonicalSchema, ParsedChatFile
from echomind.parsers.text_parser import GenericTextParser
from echomind.parsers.weflow_parser import WeFlowParser


class ParserDescriptor(CanonicalSchema):
    parser_name: str
    parser_version: str
    supported_extensions: list[str]
    available: bool


class ParserRegistry:
    """Small deterministic registry; no entry points or runtime plugins."""

    def __init__(self, parsers: Iterable[ChatParser] = ()) -> None:
        self._parsers: dict[str, ChatParser] = {}
        for parser in parsers:
            self.register(parser)

    def register(self, parser: ChatParser) -> None:
        if parser.parser_name in self._parsers:
            raise ValueError(f"Parser {parser.parser_name!r} is already registered")
        self._parsers[parser.parser_name] = parser

    def list_formats(self) -> list[ParserDescriptor]:
        return [
            ParserDescriptor(
                parser_name=parser.parser_name,
                parser_version=parser.parser_version,
                supported_extensions=sorted(parser.supported_extensions),
                available=parser.available,
            )
            for parser in sorted(self._parsers.values(), key=lambda item: item.parser_name)
        ]

    def select(self, path: Path, parser_name: str | None = None) -> ChatParser:
        filename = safe_display_name(path)
        if parser_name is not None:
            parser = self._parsers.get(parser_name)
            if parser is None:
                raise ParserError(
                    ErrorCode.UNKNOWN_PARSER,
                    safe_filename=filename,
                    message="The requested Parser is not registered.",
                    recoverable=False,
                    details={"parser_name": parser_name},
                )
            return parser

        extension = path.suffix.lower()
        extension_candidates = [
            parser for parser in self._parsers.values() if extension in parser.supported_extensions
        ]
        if not extension_candidates:
            raise ParserError(
                ErrorCode.UNSUPPORTED_EXTENSION,
                safe_filename=filename,
                message="No Parser supports this file extension.",
                recoverable=False,
                details={"extension": extension or "<none>"},
            )
        matches = [parser for parser in extension_candidates if parser.can_parse(path)]
        if not matches:
            raise ParserError(
                ErrorCode.UNSUPPORTED_FORMAT,
                safe_filename=filename,
                message="No Parser recognized a reliable format signature.",
                recoverable=False,
                details={"extension": extension},
            )
        if len(matches) > 1:
            names = sorted(parser.parser_name for parser in matches)
            raise ParserError(
                ErrorCode.AMBIGUOUS_FORMAT,
                safe_filename=filename,
                message="Multiple Parsers recognized the file; choose one explicitly.",
                recoverable=False,
                details={"parser_names": names},
            )
        return matches[0]

    def parse(
        self,
        path: Path,
        *,
        parser_name: str | None = None,
        options: ParserOptions | None = None,
    ) -> ParsedChatFile:
        return self.select(path, parser_name=parser_name).parse(path, options)


def create_default_registry() -> ParserRegistry:
    return ParserRegistry(
        [
            GenericCsvParser(),
            GenericJsonParser(),
            GenericTextParser(),
            WeFlowParser(),
        ]
    )

"""Deterministic Parser Registry selection tests."""

from pathlib import Path

import pytest

from echomind.parsers.base import ChatParser
from echomind.parsers.errors import ParserError
from echomind.parsers.options import ParserOptions
from echomind.parsers.registry import ParserRegistry, create_default_registry
from echomind.parsers.schemas import ParsedChatFile
from tests.parsers.helpers import csv_row, synthetic_json_payload, valid_text, write_csv, write_json


class MatchingParser:
    parser_name = "matching"
    parser_version = "1.0"
    supported_extensions: frozenset[str] = frozenset({".match"})
    available = True

    def can_parse(self, path: Path) -> bool:
        return path.suffix == ".match"

    def parse(self, path: Path, options: ParserOptions | None = None) -> ParsedChatFile:
        raise AssertionError("selection must not parse")

    def validate(self, result: ParsedChatFile) -> ParsedChatFile:
        return result


def test_registry_selects_each_generic_parser(tmp_path: Path) -> None:
    json_path = write_json(tmp_path / "synthetic.json", synthetic_json_payload())
    csv_path = write_csv(tmp_path / "synthetic.csv", [csv_row()])
    text_path = tmp_path / "synthetic.txt"
    text_path.write_text(valid_text(), encoding="utf-8")
    registry = create_default_registry()

    assert registry.select(json_path).parser_name == "generic-json"
    assert registry.select(csv_path).parser_name == "generic-csv"
    assert registry.select(text_path).parser_name == "generic-text"


def test_registry_allows_explicit_parser_name(tmp_path: Path) -> None:
    path = write_json(tmp_path / "synthetic.data", synthetic_json_payload())
    parser = create_default_registry().select(path, parser_name="generic-json")

    assert parser.parser_name == "generic-json"


def test_registry_reports_unknown_explicit_parser(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ParserError, match="not registered") as captured:
        create_default_registry().select(path, parser_name="missing")

    assert captured.value.error_code == "unknown_parser"


def test_registry_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.xml"
    path.write_text("<synthetic />", encoding="utf-8")

    with pytest.raises(ParserError) as captured:
        create_default_registry().select(path)

    assert captured.value.error_code == "unsupported_extension"


def test_registry_reports_no_signature_match(tmp_path: Path) -> None:
    path = tmp_path / "unknown.json"
    path.write_text('{"kind":"unknown"}', encoding="utf-8")

    with pytest.raises(ParserError) as captured:
        create_default_registry().select(path)

    assert captured.value.error_code == "unsupported_format"


def test_registry_reports_ambiguity_instead_of_using_registration_order(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.match"
    path.write_text("synthetic", encoding="utf-8")
    first: ChatParser = MatchingParser()

    class SecondMatchingParser(MatchingParser):
        parser_name = "matching-two"

    registry = ParserRegistry([first, SecondMatchingParser()])

    with pytest.raises(ParserError) as captured:
        registry.select(path)

    assert captured.value.error_code == "ambiguous_format"
    assert captured.value.details == {"parser_names": ["matching", "matching-two"]}


def test_registry_rejects_duplicate_parser_names() -> None:
    registry = ParserRegistry([MatchingParser()])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(MatchingParser())


def test_weflow_is_not_misidentified_as_supported_json(tmp_path: Path) -> None:
    path = tmp_path / "weflow-export.json"
    path.write_text('{"exporter":"weflow","records":[]}', encoding="utf-8")

    with pytest.raises(ParserError) as captured:
        create_default_registry().select(path)

    assert captured.value.error_code == "unsupported_format"


def test_supported_format_listing_marks_weflow_unavailable() -> None:
    formats = create_default_registry().list_formats()

    assert [item.parser_name for item in formats] == [
        "generic-csv",
        "generic-json",
        "generic-text",
        "weflow",
    ]
    assert next(item for item in formats if item.parser_name == "weflow").available is False

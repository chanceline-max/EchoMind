"""WeFlow stays explicit and unsupported without authorized samples."""

from pathlib import Path

import pytest

from echomind.parsers.errors import ParserError
from echomind.parsers.registry import create_default_registry
from echomind.parsers.weflow_parser import WeFlowParser


def test_weflow_never_claims_json_by_extension(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    path.write_text('{"exporter":"weflow"}', encoding="utf-8")

    assert WeFlowParser().can_parse(path) is False


def test_explicit_weflow_parse_returns_sample_required_error(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    path.write_text('{"exporter":"weflow"}', encoding="utf-8")

    with pytest.raises(ParserError) as captured:
        create_default_registry().parse(path, parser_name="weflow")

    assert captured.value.error_code == "sample_required"
    assert captured.value.parser_name == "weflow"
    assert captured.value.recoverable is False


def test_weflow_error_does_not_include_input_content(tmp_path: Path) -> None:
    canary = "PRIVATE-WEFLOW-CANARY"
    path = tmp_path / "synthetic.json"
    path.write_text(canary, encoding="utf-8")

    with pytest.raises(ParserError) as captured:
        WeFlowParser().parse(path)

    assert canary not in str(captured.value)

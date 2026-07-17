"""Generic CSV Parser tests."""

from pathlib import Path

import pytest

from echomind.parsers.csv_parser import GenericCsvParser
from echomind.parsers.errors import ParserError
from echomind.parsers.options import ErrorMode, ParserOptions
from tests.parsers.helpers import CSV_HEADERS, csv_row, write_csv


def test_valid_csv_aggregates_conversations_and_participants(tmp_path: Path) -> None:
    rows = [
        csv_row(),
        csv_row(
            conversation_id="conversation-1",
            message_id="message-2",
            sender_id="person-b",
            sender_name="Person B",
            is_profile_owner="false",
            content="Synthetic reply",
            reply_to_message_id="message-1",
        ),
        csv_row(
            conversation_id="conversation-2",
            conversation_title="Synthetic second conversation",
        ),
    ]
    path = write_csv(tmp_path / "synthetic.csv", rows)

    result = GenericCsvParser().parse(path)

    assert result.statistics.conversation_count == 2
    assert result.statistics.participant_count == 3
    assert len(result.conversations[0].participants) == 2
    assert result.conversations[0].messages[1].reply_to_source_message_id == "message-1"


def test_utf8_bom_and_quoted_multiline_content_are_supported(tmp_path: Path) -> None:
    content = 'Synthetic, quoted message\nwith a second line and "quotes"'
    path = write_csv(tmp_path / "synthetic.csv", [csv_row(content=content)], bom=True)

    result = GenericCsvParser().parse(path)

    assert result.conversations[0].messages[0].raw_content == content


def test_missing_or_extra_headers_fail_as_whole_file(tmp_path: Path) -> None:
    missing = write_csv(
        tmp_path / "missing.csv",
        [csv_row()],
        headers=[header for header in CSV_HEADERS if header != "timestamp"],
    )
    extra = write_csv(
        tmp_path / "extra.csv",
        [csv_row(unexpected="value")],
        headers=[*CSV_HEADERS, "unexpected"],
    )

    for path in [missing, extra]:
        with pytest.raises(ParserError) as captured:
            GenericCsvParser().parse(path)
        assert captured.value.error_code == "invalid_headers"


def test_empty_csv_fails(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")

    with pytest.raises(ParserError) as captured:
        GenericCsvParser().parse(path)

    assert captured.value.error_code == "invalid_headers"


@pytest.mark.parametrize(
    ("rows", "error_code"),
    [
        ([csv_row(), csv_row()], "duplicate_message"),
        (
            [csv_row(), csv_row(message_id="message-2", sender_name="Conflicting Name")],
            "participant_conflict",
        ),
        ([csv_row(is_profile_owner="maybe")], "invalid_boolean"),
        ([csv_row(timestamp="not-a-time")], "invalid_timestamp"),
        ([csv_row(reply_to_message_id="missing-message")], "unknown_reply"),
        ([csv_row(message_type="sticker")], "unsupported_message_type"),
    ],
)
def test_invalid_rows_and_cross_record_errors(
    tmp_path: Path,
    rows: list[dict[str, str]],
    error_code: str,
) -> None:
    path = write_csv(tmp_path / "synthetic.csv", rows)

    with pytest.raises(ParserError) as captured:
        GenericCsvParser().parse(path)

    assert captured.value.error_code == error_code
    assert captured.value.location is not None


def test_lenient_mode_skips_invalid_row_and_reports_physical_line(tmp_path: Path) -> None:
    rows = [csv_row(), csv_row(message_id="bad", timestamp="invalid")]
    path = write_csv(tmp_path / "synthetic.csv", rows)

    result = GenericCsvParser().parse(path, ParserOptions(error_mode=ErrorMode.LENIENT))

    assert result.statistics.message_count == 1
    assert result.statistics.skipped_record_count == 1
    assert result.warnings[0].location == "line:3"


def test_lenient_mode_without_valid_message_fails(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "synthetic.csv", [csv_row(timestamp="invalid")])

    with pytest.raises(ParserError) as captured:
        GenericCsvParser().parse(path, ParserOptions(error_mode=ErrorMode.LENIENT))

    assert captured.value.error_code == "no_valid_messages"


def test_invalid_encoding_fails_without_detection(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.csv"
    path.write_bytes(b"\xff\xfecontent")

    with pytest.raises(ParserError) as captured:
        GenericCsvParser().parse(path)

    assert captured.value.error_code == "encoding_error"


def test_large_csv_basic_behavior(tmp_path: Path) -> None:
    rows = [
        csv_row(
            message_id=f"message-{index}",
            timestamp=f"2026-07-16T10:{index // 60:02d}:{index % 60:02d}+08:00",
        )
        for index in range(600)
    ]
    path = write_csv(tmp_path / "large-synthetic.csv", rows)

    assert GenericCsvParser().parse(path).statistics.message_count == 600

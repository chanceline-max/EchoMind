"""Fixed synthetic plain-text Parser tests."""

from pathlib import Path

import pytest

from echomind.parsers.errors import ParserError
from echomind.parsers.options import ErrorMode, ParserOptions
from echomind.parsers.text_parser import GenericTextParser
from tests.parsers.helpers import valid_text


def test_valid_text_headers_and_message(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.txt"
    path.write_text(valid_text(), encoding="utf-8")

    result = GenericTextParser().parse(path)

    conversation = result.conversations[0]
    assert conversation.source_conversation_id == "conversation-1"
    assert len(conversation.participants) == 2
    assert conversation.messages[0].raw_content == "Synthetic message one"


def test_file_timezone_and_explicit_option_timezone(tmp_path: Path) -> None:
    with_header = tmp_path / "with-timezone.txt"
    with_header.write_text(valid_text(), encoding="utf-8")
    from_option = tmp_path / "with-option.txt"
    from_option.write_text(valid_text(timezone=None), encoding="utf-8")

    header_result = GenericTextParser().parse(with_header)
    option_result = GenericTextParser().parse(
        from_option,
        ParserOptions(default_timezone="Asia/Shanghai"),
    )

    header_offset = header_result.conversations[0].messages[0].timestamp.utcoffset()
    option_offset = option_result.conversations[0].messages[0].timestamp.utcoffset()
    assert header_offset is not None and header_offset.total_seconds() == 28800
    assert option_offset is not None and option_offset.total_seconds() == 28800


def test_missing_timezone_is_not_assumed_from_operating_system(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.txt"
    path.write_text(valid_text(timezone=None), encoding="utf-8")

    with pytest.raises(ParserError) as captured:
        GenericTextParser().parse(path)

    assert captured.value.error_code == "missing_timezone"


@pytest.mark.parametrize(
    ("text", "error_code"),
    [
        (
            valid_text("[message-1][2026-07-16 10:20:00] <missing-person> Synthetic message"),
            "unknown_sender",
        ),
        (
            valid_text().replace(
                "# participant: person-b|Person B|other",
                "# participant: person-a|Person B|other",
            ),
            "duplicate_participant",
        ),
        (
            valid_text(
                "[message-1][2026-07-16 10:20:00] <person-a> Synthetic one",
                "[message-1][2026-07-16 10:21:00] <person-b> Synthetic two",
            ),
            "duplicate_message",
        ),
    ],
)
def test_identity_and_reference_errors(
    tmp_path: Path,
    text: str,
    error_code: str,
) -> None:
    path = tmp_path / "synthetic.txt"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ParserError) as captured:
        GenericTextParser().parse(path)

    assert captured.value.error_code == error_code


def test_invalid_line_and_empty_content_strict_vs_lenient(tmp_path: Path) -> None:
    parser = GenericTextParser()
    strict_path = tmp_path / "strict.txt"
    strict_path.write_text(
        valid_text("This is not a message record"),
        encoding="utf-8",
    )
    lenient_path = tmp_path / "lenient.txt"
    lenient_path.write_text(
        valid_text(
            "This is not a message record",
            "[empty-message][2026-07-16 10:20:30] <person-a>    ",
            "[message-2][2026-07-16 10:21:00] <person-b> Synthetic valid message",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ParserError) as captured:
        parser.parse(strict_path)
    result = parser.parse(lenient_path, ParserOptions(error_mode=ErrorMode.LENIENT))

    assert captured.value.error_code == "invalid_record"
    assert captured.value.location == "line:7"
    assert result.statistics.message_count == 1
    assert result.statistics.skipped_record_count == 2
    assert [warning.location for warning in result.warnings] == ["line:7", "line:8"]


def test_same_timestamp_uses_stable_source_order(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.txt"
    path.write_text(
        valid_text(
            "[message-2][2026-07-16 10:20:00] <person-b> Synthetic second source record",
            "[message-1][2026-07-16 10:20:00] <person-a> Synthetic first identifier",
        ),
        encoding="utf-8",
    )

    result = GenericTextParser().parse(path)

    assert [item.source_message_id for item in result.conversations[0].messages] == [
        "message-2",
        "message-1",
    ]
    assert [item.source_order for item in result.conversations[0].messages] == [6, 7]


def test_text_format_does_not_invent_reply_relationships(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.txt"
    path.write_text(valid_text(), encoding="utf-8")

    message = GenericTextParser().parse(path).conversations[0].messages[0]

    assert message.reply_to_source_message_id is None


def test_empty_and_invalid_encoding_files_fail(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    encoded = tmp_path / "encoded.txt"
    encoded.write_bytes(b"\xff\xfeprivate")

    with pytest.raises(ParserError) as empty_error:
        GenericTextParser().parse(empty)
    with pytest.raises(ParserError) as encoding_error:
        GenericTextParser().parse(encoded)

    assert empty_error.value.error_code == "invalid_structure"
    assert encoding_error.value.error_code == "encoding_error"


def test_large_text_basic_behavior(tmp_path: Path) -> None:
    messages = [
        f"[message-{index}][2026-07-16 10:{index // 60:02d}:{index % 60:02d}] "
        f"<person-a> Synthetic message {index}"
        for index in range(600)
    ]
    path = tmp_path / "large-synthetic.txt"
    path.write_text(valid_text(*messages), encoding="utf-8")

    assert GenericTextParser().parse(path).statistics.message_count == 600

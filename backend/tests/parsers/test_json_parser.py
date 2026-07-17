"""Generic JSON Parser tests."""

from datetime import timedelta
from pathlib import Path

import pytest

from echomind.parsers.errors import ParserError
from echomind.parsers.json_parser import GenericJsonParser
from echomind.parsers.options import ErrorMode, ParserOptions
from tests.parsers.helpers import (
    synthetic_conversation,
    synthetic_json_payload,
    synthetic_message,
    write_json,
)


def test_valid_single_conversation_preserves_raw_content(tmp_path: Path) -> None:
    path = write_json(tmp_path / "synthetic.json", synthetic_json_payload())

    result = GenericJsonParser().parse(path)

    message = result.conversations[0].messages[0]
    assert result.statistics.message_count == 1
    assert message.raw_content == "Synthetic message one"
    assert message.normalized_content == message.raw_content
    assert message.source_order == 0


def test_optional_message_fields_default_when_omitted(tmp_path: Path) -> None:
    raw_message = synthetic_message()
    del raw_message["reply_to_message_id"]
    del raw_message["metadata_json"]
    path = write_json(
        tmp_path / "synthetic.json",
        synthetic_json_payload([synthetic_conversation(messages=[raw_message])]),
    )

    message = GenericJsonParser().parse(path).conversations[0].messages[0]

    assert message.reply_to_source_message_id is None
    assert message.metadata_json == {}


def test_valid_multiple_conversations_and_reply(tmp_path: Path) -> None:
    reply_messages = [
        synthetic_message(),
        synthetic_message(
            "message-2",
            "person-b",
            "2026-07-16T10:21:00+08:00",
            "Synthetic reply",
            reply_to_message_id="message-1",
        ),
    ]
    payload = synthetic_json_payload(
        [
            synthetic_conversation(messages=reply_messages),
            synthetic_conversation("conversation-2"),
        ]
    )
    path = write_json(tmp_path / "synthetic.json", payload)

    result = GenericJsonParser().parse(path)

    assert result.statistics.conversation_count == 2
    assert result.statistics.message_count == 3
    assert result.conversations[0].messages[1].reply_to_source_message_id == "message-1"


def test_offset_and_z_timestamps_remain_aware(tmp_path: Path) -> None:
    messages = [
        synthetic_message(timestamp="2026-07-16T02:20:00Z"),
        synthetic_message(
            "message-2",
            timestamp="2026-07-16T10:21:00+08:00",
        ),
    ]
    path = write_json(
        tmp_path / "synthetic.json",
        synthetic_json_payload([synthetic_conversation(messages=messages)]),
    )

    result = GenericJsonParser().parse(path)

    assert result.conversations[0].messages[0].timestamp.utcoffset() == timedelta(0)
    assert result.conversations[0].messages[1].timestamp.utcoffset() == timedelta(hours=8)


def test_utf8_bom_is_supported(tmp_path: Path) -> None:
    path = write_json(tmp_path / "synthetic.json", synthetic_json_payload(), bom=True)

    assert GenericJsonParser().parse(path).statistics.message_count == 1


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        ({"version": "1.0", "platform": "generic", "conversations": []}, "invalid_format"),
        (synthetic_json_payload(version="2.0"), "unsupported_version"),
        (synthetic_json_payload(unexpected=True), "invalid_structure"),
    ],
)
def test_top_level_contract_errors(
    tmp_path: Path,
    payload: dict[str, object],
    error_code: str,
) -> None:
    path = write_json(tmp_path / "synthetic.json", payload)

    with pytest.raises(ParserError) as captured:
        GenericJsonParser().parse(path)

    assert captured.value.error_code == error_code


def test_invalid_json_and_empty_file_fail_safely(tmp_path: Path) -> None:
    parser = GenericJsonParser()
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"format":', encoding="utf-8")
    empty = tmp_path / "empty.json"
    empty.write_bytes(b"")

    with pytest.raises(ParserError) as invalid_error:
        parser.parse(invalid)
    with pytest.raises(ParserError) as empty_error:
        parser.parse(empty)

    assert invalid_error.value.error_code == "invalid_json"
    assert empty_error.value.error_code == "invalid_json"


@pytest.mark.parametrize(
    ("message", "error_code"),
    [
        ({"id": "message-1"}, "missing_required_field"),
        (synthetic_message(timestamp="2026-07-16T10:20:00"), "invalid_timestamp"),
        (synthetic_message(type="sticker"), "unsupported_message_type"),
    ],
)
def test_invalid_message_fields_fail_in_strict_mode(
    tmp_path: Path,
    message: dict[str, object],
    error_code: str,
) -> None:
    payload = synthetic_json_payload([synthetic_conversation(messages=[message])])
    path = write_json(tmp_path / "synthetic.json", payload)

    with pytest.raises(ParserError) as captured:
        GenericJsonParser().parse(path)

    assert captured.value.error_code == error_code
    assert captured.value.location == "/conversations/0/messages/0"


@pytest.mark.parametrize(
    ("messages", "error_code"),
    [
        ([synthetic_message(), synthetic_message()], "duplicate_message"),
        ([synthetic_message(sender_id="missing-person")], "unknown_sender"),
        ([synthetic_message(reply_to_message_id="missing-message")], "unknown_reply"),
    ],
)
def test_cross_record_errors_are_detected(
    tmp_path: Path,
    messages: list[dict[str, object]],
    error_code: str,
) -> None:
    payload = synthetic_json_payload([synthetic_conversation(messages=messages)])
    path = write_json(tmp_path / "synthetic.json", payload)

    with pytest.raises(ParserError) as captured:
        GenericJsonParser().parse(path)

    assert captured.value.error_code == error_code


def test_lenient_mode_skips_one_bad_message_without_rewriting_source_order(
    tmp_path: Path,
) -> None:
    messages = [
        synthetic_message(),
        synthetic_message("bad-message", timestamp="not-a-time"),
        synthetic_message("message-3", timestamp="2026-07-16T10:22:00+08:00"),
    ]
    path = write_json(
        tmp_path / "synthetic.json",
        synthetic_json_payload([synthetic_conversation(messages=messages)]),
    )

    result = GenericJsonParser().parse(path, ParserOptions(error_mode=ErrorMode.LENIENT))

    assert [message.source_order for message in result.conversations[0].messages] == [0, 2]
    assert result.statistics.accepted_record_count == 2
    assert result.statistics.skipped_record_count == 1
    assert result.statistics.warning_count == 1


def test_lenient_mode_still_rejects_result_without_valid_messages(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "synthetic.json",
        synthetic_json_payload(
            [synthetic_conversation(messages=[synthetic_message(timestamp="invalid")])]
        ),
    )

    with pytest.raises(ParserError) as captured:
        GenericJsonParser().parse(path, ParserOptions(error_mode=ErrorMode.LENIENT))

    assert captured.value.error_code == "no_valid_messages"


def test_invalid_encoding_does_not_leak_bytes(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    path.write_bytes(b"\xff\xfeSECRET-CANARY")

    with pytest.raises(ParserError) as captured:
        GenericJsonParser().parse(path)

    assert captured.value.error_code == "encoding_error"
    assert "SECRET-CANARY" not in str(captured.value)


def test_error_and_logs_do_not_expose_body_or_absolute_path(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    body_marker = "PRIVATE_CHAT_BODY_SHOULD_NOT_ESCAPE"
    message = synthetic_message(timestamp="invalid", content=body_marker)
    path = write_json(
        tmp_path / "synthetic.json",
        synthetic_json_payload([synthetic_conversation(messages=[message])]),
    )

    with pytest.raises(ParserError) as captured:
        GenericJsonParser().parse(path)

    serialized_error = f"{captured.value} {captured.value.as_dict()}"
    assert captured.value.safe_filename == "synthetic.json"
    assert body_marker not in serialized_error
    assert str(tmp_path) not in serialized_error
    assert body_marker not in caplog.text


def test_large_synthetic_json_has_stable_counts(tmp_path: Path) -> None:
    messages = [
        synthetic_message(
            f"message-{index}",
            timestamp=f"2026-07-16T10:{index // 60:02d}:{index % 60:02d}+08:00",
        )
        for index in range(600)
    ]
    path = write_json(
        tmp_path / "large-synthetic.json",
        synthetic_json_payload([synthetic_conversation(messages=messages)]),
    )

    result = GenericJsonParser().parse(path)

    assert result.statistics.message_count == 600
    assert result == GenericJsonParser().parse(path)

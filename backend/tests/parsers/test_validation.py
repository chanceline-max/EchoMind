"""Canonical schema and centralized cross-record validation tests."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from echomind.parsers.errors import ParserError
from echomind.parsers.options import ErrorMode
from echomind.parsers.schemas import (
    CanonicalConversation,
    CanonicalMessage,
    CanonicalParticipant,
    MessageType,
    ParsedChatFile,
)
from echomind.parsers.validation import finalize_parsed_chat, validate_parsed_chat


def participant(identifier: str = "person-a", *, owner: bool | None = True) -> CanonicalParticipant:
    return CanonicalParticipant(
        source_participant_id=identifier,
        display_name="Synthetic Person",
        is_profile_owner=owner,
    )


def message(
    identifier: str = "message-1",
    *,
    sender: str = "person-a",
    reply: str | None = None,
    source_order: int = 0,
    timestamp: datetime | None = None,
) -> CanonicalMessage:
    return CanonicalMessage(
        source_message_id=identifier,
        sender_source_id=sender,
        timestamp=timestamp or datetime(2026, 7, 16, 2, 20, tzinfo=UTC),
        message_type=MessageType.TEXT,
        raw_content="Synthetic canonical message",
        normalized_content="Synthetic canonical message",
        reply_to_source_message_id=reply,
        source_order=source_order,
        source_location=f"record:{source_order}",
    )


def conversation(
    *,
    participants: list[CanonicalParticipant] | None = None,
    messages: list[CanonicalMessage] | None = None,
) -> CanonicalConversation:
    return CanonicalConversation(
        source_conversation_id="conversation-1",
        platform="generic",
        participants=participants if participants is not None else [participant()],
        messages=messages if messages is not None else [message()],
    )


def finalize(
    conversations: list[CanonicalConversation], mode: ErrorMode = ErrorMode.STRICT
) -> ParsedChatFile:
    return finalize_parsed_chat(
        source_filename="synthetic.json",
        file_hash="a" * 64,
        parser_name="synthetic-parser",
        parser_version="1.0",
        conversations=conversations,
        warnings=[],
        skipped_record_count=0,
        error_mode=mode,
    )


def test_sender_and_reply_must_exist_in_same_conversation() -> None:
    with pytest.raises(ParserError) as sender_error:
        finalize([conversation(messages=[message(sender="missing")])])
    with pytest.raises(ParserError) as reply_error:
        finalize([conversation(messages=[message(reply="missing")])])

    assert sender_error.value.error_code == "unknown_sender"
    assert reply_error.value.error_code == "unknown_reply"


def test_lenient_unknown_sender_skip_preserves_counts_order_and_references() -> None:
    result = finalize(
        [
            conversation(
                messages=[
                    message("message-1", source_order=0),
                    message("bad-sender", sender="missing", source_order=1),
                    message("message-3", source_order=2),
                ]
            )
        ],
        ErrorMode.LENIENT,
    )
    parsed = result.conversations[0]
    participant_ids = {
        item.source_participant_id
        for item in parsed.participants
        if item.source_participant_id is not None
    }

    assert result.statistics.accepted_record_count == 2
    assert result.statistics.skipped_record_count == 1
    assert [item.source_order for item in parsed.messages] == [0, 2]
    assert all(item.sender_source_id in participant_ids for item in parsed.messages)


def test_lenient_reply_skip_cascades_until_no_dangling_reference_remains() -> None:
    result = finalize(
        [
            conversation(
                messages=[
                    message("message-a", sender="missing", source_order=0),
                    message("message-b", reply="message-a", source_order=1),
                    message("message-c", reply="message-b", source_order=2),
                    message("message-d", source_order=3),
                ]
            )
        ],
        ErrorMode.LENIENT,
    )
    parsed = result.conversations[0]
    message_ids = {item.source_message_id for item in parsed.messages}

    assert [item.source_message_id for item in parsed.messages] == ["message-d"]
    assert result.statistics.accepted_record_count == 1
    assert result.statistics.skipped_record_count == 3
    assert [warning.error_code for warning in result.warnings] == [
        "unknown_sender",
        "unknown_reply",
        "unknown_reply",
    ]
    assert all(
        item.reply_to_source_message_id is None or item.reply_to_source_message_id in message_ids
        for item in parsed.messages
    )


def test_strict_reference_validation_stops_at_first_related_error() -> None:
    with pytest.raises(ParserError) as captured:
        finalize(
            [
                conversation(
                    messages=[
                        message("message-a", sender="missing", source_order=0),
                        message("message-b", reply="message-a", source_order=1),
                    ]
                )
            ]
        )

    assert captured.value.error_code == "unknown_sender"
    assert captured.value.location == "record:0"


def test_profile_owner_count_and_identifiers_are_unique() -> None:
    with pytest.raises(ParserError) as owner_error:
        finalize([conversation(participants=[participant("a"), participant("b")])])
    with pytest.raises(ParserError) as participant_error:
        finalize(
            [
                conversation(
                    participants=[participant("person-a"), participant("person-a", owner=False)]
                )
            ]
        )

    assert owner_error.value.error_code == "multiple_profile_owners"
    assert participant_error.value.error_code == "duplicate_participant"


def test_sorting_preserves_source_order_for_equal_instants() -> None:
    same = datetime(2026, 7, 16, 2, 20, tzinfo=UTC)
    result = finalize(
        [
            conversation(
                messages=[
                    message("later-source", source_order=4, timestamp=same),
                    message("earlier-source", source_order=2, timestamp=same),
                ]
            )
        ]
    )

    assert [item.source_order for item in result.conversations[0].messages] == [2, 4]


def test_time_range_is_derived_from_aware_message_instants() -> None:
    first = datetime(2026, 7, 16, 10, 20, tzinfo=timezone(timedelta(hours=8)))
    second = datetime(2026, 7, 16, 3, 21, tzinfo=UTC)
    result = finalize(
        [conversation(messages=[message(timestamp=second), message("message-2", timestamp=first)])]
    )
    parsed = result.conversations[0]

    assert parsed.started_at == first
    assert parsed.ended_at == second
    assert parsed.time_range_derived is True


def test_statistics_match_actual_canonical_data() -> None:
    result = finalize([conversation()])

    assert result.statistics.conversation_count == len(result.conversations)
    assert result.statistics.message_count == 1
    assert result.statistics.accepted_record_count == 1
    assert validate_parsed_chat(result) is result


def test_repeated_validation_is_idempotent_for_warnings_statistics_and_order() -> None:
    early = datetime(2026, 7, 16, 2, 20, tzinfo=UTC)
    late = datetime(2026, 7, 16, 2, 30, tzinfo=UTC)
    result = finalize(
        [
            conversation(
                messages=[
                    message("late", source_order=4, timestamp=late),
                    message("bad", sender="missing", source_order=1, timestamp=early),
                    message("early", source_order=2, timestamp=early),
                ]
            )
        ],
        ErrorMode.LENIENT,
    )
    original = result.model_dump_json()

    first = validate_parsed_chat(result)
    after_first = first.model_dump_json()
    second = validate_parsed_chat(first)

    assert first is result
    assert second is result
    assert original == after_first == second.model_dump_json()
    assert result.statistics.skipped_record_count == 1
    assert result.statistics.warning_count == 1
    assert len(result.warnings) == 1
    assert result.conversations[0].time_range_derived is True
    assert [item.source_order for item in result.conversations[0].messages] == [2, 4]


def test_empty_results_are_rejected() -> None:
    with pytest.raises(ParserError) as no_conversations:
        finalize([])
    with pytest.raises(ParserError) as no_messages:
        finalize([conversation(messages=[])])

    assert no_conversations.value.error_code == "no_valid_conversations"
    assert no_messages.value.error_code == "no_valid_messages"


def test_schema_rejects_unknown_fields_and_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        CanonicalParticipant.model_validate(
            {
                "source_participant_id": "person-a",
                "display_name": "Person A",
                "unexpected": "not allowed",
            }
        )
    with pytest.raises(ValidationError):
        CanonicalMessage.model_validate(
            {
                "source_message_id": "message-1",
                "sender_source_id": "person-a",
                "timestamp": datetime(2026, 7, 16, 10, 20),
                "message_type": "text",
                "raw_content": "Synthetic",
                "normalized_content": "Synthetic",
                "source_order": 0,
            }
        )


def test_text_message_cannot_be_empty_but_attachment_placeholder_can() -> None:
    with pytest.raises(ValidationError):
        CanonicalMessage(
            source_message_id="message-1",
            sender_source_id="person-a",
            timestamp=datetime(2026, 7, 16, 2, 20, tzinfo=UTC),
            message_type=MessageType.TEXT,
            raw_content="  ",
            normalized_content="  ",
            source_order=0,
        )

    attachment = CanonicalMessage(
        source_message_id="message-2",
        sender_source_id="person-a",
        timestamp=datetime(2026, 7, 16, 2, 20, tzinfo=UTC),
        message_type=MessageType.IMAGE,
        raw_content="",
        normalized_content="",
        source_order=1,
        metadata_json={"placeholder": True},
    )
    assert attachment.raw_content == ""

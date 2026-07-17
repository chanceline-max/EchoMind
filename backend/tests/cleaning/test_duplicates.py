"""Conservative exact duplicate detection tests."""

from echomind.cleaning.options import CleaningOptions, RedactionCategory
from echomind.cleaning.pipeline import clean_chat
from echomind.parsers.schemas import CanonicalMessage, MessageType

from .factories import conversation, message, parsed_chat, participant


def duplicate_ids(messages: list[CanonicalMessage]) -> list[str | None]:
    source = parsed_chat([conversation(messages)])
    cleaned = clean_chat(source).conversations[0].cleaned_messages
    return [item.duplicate_of_source_message_id for item in cleaned]


def test_exact_duplicate_marks_only_later_occurrence() -> None:
    messages = [
        message("message-1", source_order=0),
        message("message-2", source_order=1),
    ]

    assert duplicate_ids(messages) == [None, "message-1"]


def test_duplicate_detection_preserves_messages_and_source_order() -> None:
    source = parsed_chat(
        [conversation([message("first", source_order=4), message("second", source_order=9)])]
    )

    result = clean_chat(source)
    cleaned = result.conversations[0].cleaned_messages

    assert [item.source_message_id for item in cleaned] == ["first", "second"]
    assert [item.source_order for item in cleaned] == [4, 9]
    assert result.statistics.output_message_count == 2


def test_different_sender_is_not_duplicate() -> None:
    assert duplicate_ids(
        [message("first", sender="person-a"), message("second", sender="person-b")]
    ) == [None, None]


def test_different_timestamp_is_not_duplicate() -> None:
    assert duplicate_ids([message("first"), message("second", seconds=1)]) == [None, None]


def test_different_reply_target_is_not_duplicate() -> None:
    messages = [
        message("root", content="Root", source_order=0),
        message("first", reply="root", source_order=1),
        message("second", reply=None, source_order=2),
    ]

    assert duplicate_ids(messages) == [None, None, None]


def test_different_message_type_is_not_duplicate() -> None:
    messages = [
        message("first", message_type=MessageType.IMAGE, source_order=0),
        message("second", message_type=MessageType.FILE, source_order=1),
    ]

    assert duplicate_ids(messages) == [None, None]


def test_duplicate_detection_does_not_cross_conversations() -> None:
    source = parsed_chat(
        [
            conversation([message("first")], identifier="conversation-1"),
            conversation([message("second")], identifier="conversation-2"),
        ]
    )

    result = clean_chat(source)

    assert all(
        item.duplicate_of_source_message_id is None
        for conversation_item in result.conversations
        for item in conversation_item.cleaned_messages
    )


def test_url_replacement_does_not_create_false_duplicate() -> None:
    messages = [
        message("first", content="https://first.invalid", source_order=0),
        message("second", content="https://second.invalid", source_order=1),
    ]

    assert duplicate_ids(messages) == [None, None]


def test_redaction_does_not_create_false_duplicate() -> None:
    source = parsed_chat(
        [
            conversation(
                [
                    message("first", content="one@example.invalid", source_order=0),
                    message("second", content="two@example.invalid", source_order=1),
                ]
            )
        ]
    )
    options = CleaningOptions(
        redact_sensitive_data=True,
        redaction_categories={RedactionCategory.EMAIL},
    )

    cleaned = clean_chat(source, options).conversations[0].cleaned_messages

    assert [item.normalized_content for item in cleaned] == ["[EMAIL]", "[EMAIL]"]
    assert [item.duplicate_of_source_message_id for item in cleaned] == [None, None]


def test_duplicate_detection_can_be_disabled_and_is_stable() -> None:
    source = parsed_chat(
        [conversation([message("first", source_order=0), message("second", source_order=1)])]
    )

    disabled = clean_chat(source, CleaningOptions(detect_exact_duplicates=False))
    first = clean_chat(source)
    second = clean_chat(source)

    assert all(
        item.duplicate_of_source_message_id is None
        for item in disabled.conversations[0].cleaned_messages
    )
    assert first.model_dump_json() == second.model_dump_json()


def test_duplicate_target_always_exists_earlier_in_same_conversation() -> None:
    source = parsed_chat(
        [
            conversation(
                [
                    message("first", source_order=5),
                    message("second", source_order=6),
                    message("third", source_order=7),
                ],
                participants=[participant("person-a")],
            )
        ]
    )

    cleaned = clean_chat(source).conversations[0].cleaned_messages

    assert [item.duplicate_of_source_message_id for item in cleaned] == [None, "first", "first"]

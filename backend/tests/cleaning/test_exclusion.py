"""Message exclusion policy tests."""

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat
from echomind.cleaning.schemas import ExclusionReason
from echomind.parsers.schemas import MessageType

from .factories import conversation, message, parsed_chat


def test_default_policy_excludes_system_recalled_and_duplicate_messages() -> None:
    source = parsed_chat(
        [
            conversation(
                [
                    message(
                        "system", content="event", message_type=MessageType.SYSTEM, source_order=0
                    ),
                    message("recalled", content="撤回了一条消息", source_order=1),
                    message("first", content="duplicate", source_order=2),
                    message("second", content="duplicate", source_order=3),
                ]
            )
        ]
    )

    cleaned = clean_chat(source).conversations[0].cleaned_messages

    assert [item.exclusion_reasons for item in cleaned] == [
        [ExclusionReason.SYSTEM_MESSAGE],
        [ExclusionReason.RECALLED_MESSAGE],
        [],
        [ExclusionReason.EXACT_DUPLICATE],
    ]
    assert all(item.raw_content for item in cleaned)


def test_exclusion_switches_are_independent_from_classification() -> None:
    source = parsed_chat(
        [
            conversation(
                [
                    message(
                        "system", content="event", message_type=MessageType.SYSTEM, source_order=0
                    ),
                    message("recalled", content="撤回了一条消息", source_order=1),
                    message("first", content="same", source_order=2),
                    message("second", content="same", source_order=3),
                ]
            )
        ]
    )
    options = CleaningOptions(
        exclude_system_messages=False,
        exclude_recalled_messages=False,
        exclude_duplicates=False,
    )

    cleaned = clean_chat(source, options).conversations[0].cleaned_messages

    assert cleaned[0].is_system_message is True
    assert cleaned[1].is_recalled_message is True
    assert cleaned[3].duplicate_of_source_message_id == "first"
    assert all(item.excluded_from_analysis is False for item in cleaned)


def test_user_explicit_exclusion_is_supported() -> None:
    options = CleaningOptions(excluded_source_message_ids={"message-1"})

    cleaned = clean_chat(parsed_chat(), options).conversations[0].cleaned_messages[0]

    assert cleaned.excluded_from_analysis is True
    assert cleaned.exclusion_reasons == [ExclusionReason.USER_EXCLUDED]


def test_message_can_have_multiple_stable_exclusion_reasons_without_duplicates() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(
        content="撤回了一条消息", message_type=MessageType.SYSTEM
    )
    options = CleaningOptions(excluded_source_message_ids={"message-1"})

    first = clean_chat(source, options)
    second = clean_chat(source, options)
    cleaned = first.conversations[0].cleaned_messages[0]

    assert cleaned.exclusion_reasons == [
        ExclusionReason.SYSTEM_MESSAGE,
        ExclusionReason.RECALLED_MESSAGE,
        ExclusionReason.USER_EXCLUDED,
    ]
    assert first.model_dump_json() == second.model_dump_json()


def test_exclusion_preserves_reply_reference_and_all_messages() -> None:
    source = parsed_chat(
        [
            conversation(
                [
                    message("excluded", content="Root", source_order=0),
                    message("reply", content="Reply", source_order=1, reply="excluded"),
                ]
            )
        ]
    )
    options = CleaningOptions(excluded_source_message_ids={"excluded"})

    cleaned = clean_chat(source, options).conversations[0].cleaned_messages

    assert len(cleaned) == 2
    assert cleaned[1].reply_to_source_message_id == "excluded"

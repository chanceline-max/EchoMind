"""Attachment placeholder tests."""

import pytest

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat
from echomind.parsers.schemas import MessageType

from .factories import message, parsed_chat


@pytest.mark.parametrize(
    ("message_type", "placeholder"),
    [
        (MessageType.IMAGE, "[IMAGE]"),
        (MessageType.FILE, "[FILE]"),
        (MessageType.AUDIO, "[AUDIO]"),
        (MessageType.VIDEO, "[VIDEO]"),
        (MessageType.OTHER, "[ATTACHMENT]"),
    ],
)
def test_empty_attachment_gets_deterministic_placeholder(
    message_type: MessageType, placeholder: str
) -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content="", message_type=message_type)

    cleaned = clean_chat(source).conversations[0].cleaned_messages[0]

    assert cleaned.raw_content == ""
    assert cleaned.normalized_content == placeholder


def test_attachment_description_is_preserved() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(
        content="Synthetic caption", message_type=MessageType.IMAGE
    )

    cleaned = clean_chat(source).conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == "Synthetic caption"


@pytest.mark.parametrize("message_type", [MessageType.TEXT, MessageType.SYSTEM])
def test_text_and_system_messages_never_get_attachment_placeholder(
    message_type: MessageType,
) -> None:
    source = parsed_chat()
    content = "" if message_type is MessageType.SYSTEM else "Synthetic"
    source.conversations[0].messages[0] = message(content=content, message_type=message_type)

    cleaned = clean_chat(source).conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == content


def test_attachment_cleaner_can_be_disabled_and_is_idempotent() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content="", message_type=MessageType.FILE)

    disabled = clean_chat(source, CleaningOptions(add_attachment_placeholders=False))
    first = clean_chat(source)
    second = clean_chat(source)

    assert disabled.conversations[0].cleaned_messages[0].normalized_content == ""
    assert first.model_dump_json() == second.model_dump_json()
    assert first.statistics.attachment_placeholder_count == 1

"""Deterministic system and recalled classification tests."""

from typing import Any

import pytest

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat
from echomind.cleaning.schemas import CleanedMessage
from echomind.parsers.schemas import MessageType

from .factories import message, parsed_chat


def cleaned_message(*, options: CleaningOptions | None = None, **kwargs: Any) -> CleanedMessage:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(**kwargs)
    return clean_chat(source, options).conversations[0].cleaned_messages[0]


def test_message_type_system_is_classified() -> None:
    cleaned = cleaned_message(content="Synthetic event", message_type=MessageType.SYSTEM)

    assert cleaned.is_system_message is True


@pytest.mark.parametrize("key", ["is_system_message", "system_message"])
def test_explicit_boolean_metadata_classifies_system_message(key: str) -> None:
    cleaned = cleaned_message(metadata={key: True})

    assert cleaned.is_system_message is True


def test_string_metadata_does_not_count_as_explicit_boolean_marker() -> None:
    cleaned = cleaned_message(metadata={"is_system_message": "true"})

    assert cleaned.is_system_message is False


@pytest.mark.parametrize(
    "content",
    [
        "You recalled a message",
        "Person A recalled a message",
        "撤回了一条消息",
        "用户甲撤回了一条消息",
    ],
)
def test_exact_recalled_placeholders_are_classified(content: str) -> None:
    cleaned = cleaned_message(content=content)

    assert cleaned.is_recalled_message is True


@pytest.mark.parametrize(
    "content",
    [
        "我撤回刚才的意见",
        "系统思维很重要",
        "这是一个通知功能",
        "The phrase recalled a message appears in a longer sentence today",
    ],
)
def test_ordinary_chat_is_not_misclassified(content: str) -> None:
    cleaned = cleaned_message(content=content)

    assert cleaned.is_system_message is False
    assert cleaned.is_recalled_message is False


def test_classification_is_separate_from_exclusion() -> None:
    options = CleaningOptions(exclude_system_messages=False, exclude_recalled_messages=False)
    cleaned = cleaned_message(
        options=options,
        content="You recalled a message",
        message_type=MessageType.SYSTEM,
    )

    assert cleaned.is_system_message is True
    assert cleaned.is_recalled_message is True
    assert cleaned.excluded_from_analysis is False


def test_classification_switches_are_independent() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(
        content="You recalled a message", message_type=MessageType.SYSTEM
    )

    result = clean_chat(
        source,
        CleaningOptions(
            classify_system_messages=False,
            classify_recalled_messages=False,
            exclude_system_messages=False,
            exclude_recalled_messages=False,
        ),
    )
    cleaned = result.conversations[0].cleaned_messages[0]

    assert cleaned.is_system_message is False
    assert cleaned.is_recalled_message is False


def test_classification_operations_record_rule_names_not_content() -> None:
    cleaned = cleaned_message(content="You recalled a message", message_type=MessageType.SYSTEM)
    serialized = [operation.model_dump() for operation in cleaned.cleaning_operations]

    assert {item["cleaner_name"] for item in serialized} >= {
        "system_classification",
        "recalled_classification",
    }
    assert "You recalled a message" not in str(serialized)

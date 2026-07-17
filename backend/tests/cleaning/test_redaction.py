"""Opt-in deterministic redaction tests."""

import pytest
from pydantic import ValidationError

from echomind.cleaning.options import (
    CleaningOptions,
    CustomRedactionPattern,
    RedactionCategory,
)
from echomind.cleaning.pipeline import clean_chat
from echomind.cleaning.schemas import CleanedChatFile

from .factories import message, parsed_chat


def redact(content: str, options: CleaningOptions) -> CleanedChatFile:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content=content)
    return clean_chat(source, options)


def test_redaction_is_disabled_by_default() -> None:
    result = redact("person@example.invalid +8613800138000 192.0.2.1", CleaningOptions())
    cleaned = result.conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == "person@example.invalid +8613800138000 192.0.2.1"
    assert result.statistics.redaction_count == 0


@pytest.mark.parametrize(
    ("category", "content", "expected"),
    [
        (RedactionCategory.EMAIL, "person@example.invalid", "[EMAIL]"),
        (RedactionCategory.PHONE_LIKE, "+86 138 0013 8000", "[PHONE]"),
        (RedactionCategory.IPV4, "192.0.2.25", "[IP]"),
    ],
)
def test_supported_category_redacts_deterministically(
    category: RedactionCategory, content: str, expected: str
) -> None:
    result = redact(
        content,
        CleaningOptions(redact_sensitive_data=True, redaction_categories={category}),
    )

    assert result.conversations[0].cleaned_messages[0].normalized_content == expected


def test_multiple_categories_count_each_replacement() -> None:
    content = "person@example.invalid +86 138 0013 8000 192.0.2.25"
    result = redact(content, CleaningOptions(redact_sensitive_data=True))

    assert result.conversations[0].cleaned_messages[0].normalized_content == (
        "[EMAIL] [PHONE] [IP]"
    )
    assert result.statistics.redacted_message_count == 1
    assert result.statistics.redaction_count == 3


def test_custom_simple_pattern_is_opt_in_and_uses_controlled_placeholder() -> None:
    options = CleaningOptions(
        redact_sensitive_data=True,
        redaction_categories={RedactionCategory.CUSTOM},
        custom_redaction_patterns=[
            CustomRedactionPattern(
                name="synthetic_identifier",
                pattern=r"SYN-\d{4}",
                placeholder="[SYNTHETIC_ID]",
            )
        ],
    )

    result = redact("Reference SYN-1234", options)

    assert result.conversations[0].cleaned_messages[0].normalized_content == (
        "Reference [SYNTHETIC_ID]"
    )


def test_custom_patterns_are_ignored_unless_custom_category_is_enabled() -> None:
    options = CleaningOptions(
        redact_sensitive_data=True,
        redaction_categories={RedactionCategory.EMAIL},
        custom_redaction_patterns=[CustomRedactionPattern(name="synthetic", pattern=r"SYN-\d{4}")],
    )

    result = redact("SYN-1234", options)

    assert result.conversations[0].cleaned_messages[0].normalized_content == "SYN-1234"


@pytest.mark.parametrize(
    "content",
    [
        "13800138000",
        "Call extension 12345",
        "999.0.2.1",
        "version 1.2.3.4.5",
        "name@localhost",
    ],
)
def test_conservative_redaction_avoids_documented_false_positive_boundaries(
    content: str,
) -> None:
    result = redact(content, CleaningOptions(redact_sensitive_data=True))

    assert result.conversations[0].cleaned_messages[0].normalized_content == content


def test_redaction_never_changes_raw_or_records_original_values() -> None:
    original = "private.person@example.invalid"
    result = redact(original, CleaningOptions(redact_sensitive_data=True))
    cleaned = result.conversations[0].cleaned_messages[0]

    assert cleaned.raw_content == original
    assert original not in str([item.model_dump() for item in cleaned.cleaning_operations])


def test_redaction_is_idempotent_for_same_parser_input() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content="person@example.invalid")
    options = CleaningOptions(redact_sensitive_data=True)

    first = clean_chat(source, options)
    second = clean_chat(source, options)

    assert first.model_dump_json() == second.model_dump_json()
    assert first.statistics.redaction_count == 1


def test_custom_placeholder_must_be_safe_and_controlled() -> None:
    with pytest.raises(ValidationError):
        CustomRedactionPattern(name="unsafe", pattern="SYN", placeholder="raw value")

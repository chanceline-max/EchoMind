"""Conservative URL placeholder tests."""

import pytest

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat

from .factories import message, parsed_chat


@pytest.mark.parametrize(
    ("content", "expected", "count"),
    [
        ("Open http://example.invalid now", "Open [URL] now", 1),
        ("Open https://example.invalid/path now", "Open [URL] now", 1),
        ("http://one.invalid and https://two.invalid", "[URL] and [URL]", 2),
        ("See https://example.invalid/path, then continue.", "See [URL], then continue.", 1),
        ("Email person@example.invalid", "Email person@example.invalid", 0),
        ("Visit example.invalid", "Visit example.invalid", 0),
        ("Already [URL]", "Already [URL]", 0),
    ],
)
def test_url_replacement_is_explicit_and_preserves_punctuation(
    content: str, expected: str, count: int
) -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content=content)

    result = clean_chat(source)
    cleaned = result.conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == expected
    assert cleaned.raw_content == content
    assert result.statistics.url_replacement_count == count


def test_url_placeholder_is_configurable() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content="https://example.invalid")

    cleaned = clean_chat(source, CleaningOptions(url_placeholder="[LINK]"))

    assert cleaned.conversations[0].cleaned_messages[0].normalized_content == "[LINK]"


def test_url_replacement_can_be_disabled_and_is_idempotent() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content="https://example.invalid")

    disabled = clean_chat(source, CleaningOptions(replace_urls=False))
    first = clean_chat(source)
    second = clean_chat(source)

    assert disabled.conversations[0].cleaned_messages[0].normalized_content == (
        "https://example.invalid"
    )
    assert first.model_dump_json() == second.model_dump_json()


def test_url_operation_contains_count_but_not_original_url() -> None:
    original = "https://private.invalid/opaque"
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content=original)

    operation = next(
        item
        for item in clean_chat(source).conversations[0].cleaned_messages[0].cleaning_operations
        if item.cleaner_name == "url_replacement"
    )

    assert operation.details == {"replacement_count": 1}
    assert original not in operation.model_dump_json()

"""Conservative whitespace normalization tests."""

import pytest

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat

from .factories import message, parsed_chat


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("alpha\r\nbeta\rgamma", "alpha\nbeta\ngamma"),
        ("alpha   \n beta\t", "alpha\n beta"),
        ("  alpha beta  ", "alpha beta"),
        ("alpha\n\n\n\n beta", "alpha\n\n\n beta"),
        ("中文 English  🙂", "中文 English  🙂"),
        ("def run():\n    return 1\n\ntext", "def run():\n    return 1\n\ntext"),
    ],
)
def test_whitespace_rules_are_conservative(content: str, expected: str) -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content=content)

    cleaned = clean_chat(source).conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == expected
    assert cleaned.raw_content == content


def test_line_endings_can_be_enabled_without_other_whitespace_changes() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content="  alpha  \r\n beta  ")
    options = CleaningOptions(normalize_whitespace=False, normalize_line_endings=True)

    cleaned = clean_chat(source, options).conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == "  alpha  \n beta  "


def test_whitespace_cleaner_can_be_fully_disabled() -> None:
    content = "  alpha  \r\n beta  "
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content=content)
    options = CleaningOptions(normalize_whitespace=False, normalize_line_endings=False)

    cleaned = clean_chat(source, options).conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == content


def test_blank_line_limit_is_configurable() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content="alpha\n\n\n beta")

    cleaned = (
        clean_chat(
            source,
            CleaningOptions(max_consecutive_blank_lines=1),
        )
        .conversations[0]
        .cleaned_messages[0]
    )

    assert cleaned.normalized_content == "alpha\n\n beta"


def test_whitespace_operation_is_added_once_and_is_safe() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content=" alpha \r\n")

    first = clean_chat(source)
    second = clean_chat(source)
    operations = first.conversations[0].cleaned_messages[0].cleaning_operations

    assert len(operations) == 1
    assert operations[0].cleaner_name == "whitespace"
    assert "alpha" not in operations[0].model_dump_json()
    assert first.model_dump_json() == second.model_dump_json()

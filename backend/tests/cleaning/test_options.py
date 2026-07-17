"""Cleaning option validation tests."""

import pytest
from pydantic import ValidationError

from echomind.cleaning.options import (
    CleaningOptions,
    CustomRedactionPattern,
    RedactionCategory,
)


def test_defaults_are_explicit_and_redaction_is_opt_in() -> None:
    options = CleaningOptions()

    assert options.redact_sensitive_data is False
    assert options.normalize_whitespace is True
    assert options.build_analysis_units is True
    assert options.redaction_categories == {
        RedactionCategory.EMAIL,
        RedactionCategory.PHONE_LIKE,
        RedactionCategory.IPV4,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("analysis_unit_max_gap_seconds", -1),
        ("analysis_unit_max_gap_seconds", 86_401),
        ("analysis_unit_max_messages", 0),
        ("analysis_unit_max_messages", 101),
        ("analysis_unit_max_characters", 0),
        ("analysis_unit_max_characters", 100_001),
        ("max_consecutive_blank_lines", -1),
        ("max_consecutive_blank_lines", 11),
    ],
)
def test_numeric_options_have_bounds(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        CleaningOptions.model_validate({field: value})


def test_unknown_options_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CleaningOptions.model_validate({"future_flag": True})


def test_mutable_defaults_are_not_shared() -> None:
    first = CleaningOptions()
    second = CleaningOptions()

    assert first.redaction_categories is not second.redaction_categories
    assert first.custom_redaction_patterns is not second.custom_redaction_patterns
    assert first.excluded_source_message_ids is not second.excluded_source_message_ids


@pytest.mark.parametrize(
    "pattern",
    [
        r"(a+)+$",
        r"(?=unsafe)",
        r"(alpha|beta)",
        r".*secret",
        r"value\\1",
        r"a+",
        r"a{1,}",
        r"a{101}",
        r"\b",
    ],
)
def test_custom_patterns_reject_complex_or_backtracking_prone_regex(pattern: str) -> None:
    with pytest.raises(ValidationError):
        CustomRedactionPattern(name="unsafe", pattern=pattern)


def test_custom_pattern_count_and_length_are_limited() -> None:
    patterns = [
        CustomRedactionPattern(name=f"rule_{index}", pattern=f"ID-{index}") for index in range(11)
    ]

    with pytest.raises(ValidationError):
        CleaningOptions(custom_redaction_patterns=patterns)
    with pytest.raises(ValidationError):
        CustomRedactionPattern(name="long", pattern="a" * 201)


def test_invalid_custom_regex_fails_during_option_validation() -> None:
    with pytest.raises(ValidationError):
        CustomRedactionPattern(name="broken", pattern="[unterminated")


def test_bounded_simple_custom_regex_is_allowed() -> None:
    pattern = CustomRedactionPattern(name="bounded", pattern=r"SYN-[A-Z]{2,8}-\d{4}")

    assert pattern.pattern == r"SYN-[A-Z]{2,8}-\d{4}"

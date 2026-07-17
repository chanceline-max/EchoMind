"""Validated, host-independent cleaning configuration."""

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

SafeName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
SafePlaceholder = Annotated[
    str,
    StringConstraints(pattern=r"^\[[A-Z][A-Z0-9_]{0,30}\]$"),
]


class RedactionCategory(StrEnum):
    EMAIL = "email"
    PHONE_LIKE = "phone_like"
    IPV4 = "ipv4"
    CUSTOM = "custom"


class CustomRedactionPattern(BaseModel):
    """A deliberately limited, simple regular-expression rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: SafeName
    pattern: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    placeholder: SafePlaceholder = "[REDACTED]"

    @field_validator("pattern")
    @classmethod
    def pattern_must_be_simple_and_compilable(cls, value: str) -> str:
        # Grouping, alternation, lookarounds, backreferences and unbounded dot
        # repetition are unnecessary for deterministic first-version rules and
        # are the main source of catastrophic backtracking configurations.
        forbidden_fragments = ("(?", "|", ".*", ".+")
        if any(item in value for item in forbidden_fragments):
            raise ValueError("custom patterns must use the supported simple-regex subset")
        if re.search(r"(?<!\\)\(", value) or re.search(r"\\[1-9]", value):
            raise ValueError("custom patterns cannot use groups or backreferences")
        if re.search(r"(?<!\\)[*+]", value):
            raise ValueError("custom patterns cannot use unbounded repetition")
        for quantifier in re.finditer(r"(?<!\\)\{(\d+)(?:,(\d*))?\}", value):
            lower = int(quantifier.group(1))
            upper_text = quantifier.group(2)
            if upper_text == "":
                raise ValueError("custom pattern repetition must have an upper bound")
            upper = lower if upper_text is None else int(upper_text)
            if lower > upper or upper > 100:
                raise ValueError("custom pattern repetition bounds must be between 0 and 100")
        try:
            compiled = re.compile(value)
        except re.error as error:
            raise ValueError("custom pattern must be a valid regular expression") from error
        for probe in ("", "a", "0", " "):
            match = compiled.search(probe)
            if match is not None and match.start() == match.end():
                raise ValueError("custom patterns cannot produce zero-length matches")
        return value


class CleaningOptions(BaseModel):
    """All stage-four cleaners are controlled explicitly by this schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    normalize_whitespace: bool = True
    normalize_line_endings: bool = True
    max_consecutive_blank_lines: int = Field(default=2, ge=0, le=10)
    add_attachment_placeholders: bool = True
    classify_system_messages: bool = True
    classify_recalled_messages: bool = True
    detect_exact_duplicates: bool = True
    replace_urls: bool = True
    redact_sensitive_data: bool = False
    exclude_system_messages: bool = True
    exclude_recalled_messages: bool = True
    exclude_duplicates: bool = True
    build_analysis_units: bool = True
    url_placeholder: SafePlaceholder = "[URL]"
    analysis_unit_max_gap_seconds: int = Field(default=120, ge=0, le=86_400)
    analysis_unit_max_messages: int = Field(default=8, ge=1, le=100)
    analysis_unit_max_characters: int = Field(default=2_000, ge=1, le=100_000)
    redaction_categories: set[RedactionCategory] = Field(
        default_factory=lambda: {
            RedactionCategory.EMAIL,
            RedactionCategory.PHONE_LIKE,
            RedactionCategory.IPV4,
        }
    )
    custom_redaction_patterns: list[CustomRedactionPattern] = Field(
        default_factory=list,
        max_length=10,
    )
    excluded_source_message_ids: set[str] = Field(default_factory=set)

    @field_validator("excluded_source_message_ids")
    @classmethod
    def excluded_identifiers_must_be_non_empty(cls, values: set[str]) -> set[str]:
        if any(not value.strip() for value in values):
            raise ValueError("excluded source message identifiers cannot be blank")
        return values

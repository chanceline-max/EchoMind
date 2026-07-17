"""Database-independent output and trace schemas for cleaning."""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from echomind.cleaning.errors import CleaningErrorCode
from echomind.parsers.schemas import CanonicalParticipant, MessageType, ParseWarning

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256String = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonNegativeInt = Annotated[int, Field(ge=0)]
SafeDetailValue = int | bool | str | list[str]


class CleaningSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExclusionReason(StrEnum):
    SYSTEM_MESSAGE = "system_message"
    RECALLED_MESSAGE = "recalled_message"
    EXACT_DUPLICATE = "exact_duplicate"
    USER_EXCLUDED = "user_excluded"


_ALLOWED_CHANGED_FIELDS = frozenset(
    {
        "normalized_content",
        "is_system_message",
        "is_recalled_message",
        "duplicate_of_source_message_id",
        "excluded_from_analysis",
        "exclusion_reasons",
    }
)
_ALLOWED_DETAIL_KEYS = frozenset(
    {
        "line_ending_replacements",
        "trailing_whitespace_lines",
        "trimmed_boundary_characters",
        "collapsed_blank_line_runs",
        "placeholder",
        "rule",
        "replacement_count",
        "categories",
        "reason_count",
    }
)
_ALLOWED_RULES = frozenset(
    {
        "message_type",
        "metadata:is_system_message",
        "metadata:system_message",
        "exact_text:[SYSTEM]",
        "english_recalled_placeholder",
        "chinese_recalled_placeholder",
        "exact_match",
        "configured_policy",
    }
)


class CleaningOperation(CleaningSchema):
    cleaner_name: NonEmptyString
    cleaner_version: NonEmptyString
    operation_type: NonEmptyString
    changed_fields: list[NonEmptyString]
    details: dict[str, SafeDetailValue] = Field(default_factory=dict)

    @field_validator("changed_fields")
    @classmethod
    def changed_fields_are_controlled(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(
            item not in _ALLOWED_CHANGED_FIELDS for item in values
        ):
            raise ValueError("changed_fields contains unsupported or duplicate values")
        return values

    @field_validator("details")
    @classmethod
    def details_are_safe_structural_values(
        cls, values: dict[str, SafeDetailValue]
    ) -> dict[str, SafeDetailValue]:
        if any(key not in _ALLOWED_DETAIL_KEYS for key in values):
            raise ValueError("operation details contain an unsupported key")
        placeholder = values.get("placeholder")
        if isinstance(placeholder, str) and not re_fullmatch_placeholder(placeholder):
            raise ValueError("operation placeholder is not controlled")
        rule = values.get("rule")
        if isinstance(rule, str) and rule not in _ALLOWED_RULES:
            raise ValueError("operation rule is not controlled")
        categories = values.get("categories")
        if isinstance(categories, list) and any(
            item not in {"email", "phone_like", "ipv4", "custom"} for item in categories
        ):
            raise ValueError("operation categories are not controlled")
        return values


def re_fullmatch_placeholder(value: str) -> bool:
    if len(value) > 32 or not value.startswith("[") or not value.endswith("]"):
        return False
    inner = value[1:-1]
    return bool(inner) and all(
        character.isupper() or character.isdigit() or character == "_" for character in inner
    )


class CleaningWarning(CleaningSchema):
    error_code: CleaningErrorCode
    safe_filename: NonEmptyString
    cleaner_name: NonEmptyString | None = None
    message: str
    conversation_source_id: NonEmptyString | None = None
    message_source_id: NonEmptyString | None = None
    recoverable: bool = True
    details: dict[str, str | int | bool] = Field(default_factory=dict)

    @field_validator("safe_filename")
    @classmethod
    def filename_must_not_be_a_path(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("safe_filename must be a basename")
        return value


class CleanedMessage(CleaningSchema):
    source_message_id: NonEmptyString
    sender_source_id: NonEmptyString
    timestamp: AwareDatetime
    message_type: MessageType
    raw_content: str
    normalized_content: str
    reply_to_source_message_id: NonEmptyString | None = None
    source_order: NonNegativeInt
    source_location: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    is_system_message: bool = False
    is_recalled_message: bool = False
    duplicate_of_source_message_id: NonEmptyString | None = None
    excluded_from_analysis: bool = False
    exclusion_reasons: list[ExclusionReason] = Field(default_factory=list)
    cleaning_operations: list[CleaningOperation] = Field(default_factory=list)

    @model_validator(mode="after")
    def derived_lists_and_flags_are_consistent(self) -> "CleanedMessage":
        if len(self.exclusion_reasons) != len(set(self.exclusion_reasons)):
            raise ValueError("exclusion reasons must be unique")
        if self.excluded_from_analysis != bool(self.exclusion_reasons):
            raise ValueError("excluded flag must match exclusion reasons")
        serialized = [item.model_dump_json() for item in self.cleaning_operations]
        if len(serialized) != len(set(serialized)):
            raise ValueError("cleaning operations must be unique")
        return self


class AnalysisUnit(CleaningSchema):
    analysis_unit_id: NonEmptyString
    conversation_source_id: NonEmptyString
    sender_source_id: NonEmptyString
    message_source_ids: list[NonEmptyString] = Field(min_length=1)
    started_at: AwareDatetime
    ended_at: AwareDatetime
    combined_content: str
    message_count: int = Field(ge=1)
    source_order_start: NonNegativeInt
    source_order_end: NonNegativeInt
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def counts_and_ranges_are_consistent(self) -> "AnalysisUnit":
        if self.message_count != len(self.message_source_ids):
            raise ValueError("analysis unit message count is inconsistent")
        if self.ended_at < self.started_at or self.source_order_end < self.source_order_start:
            raise ValueError("analysis unit range is inconsistent")
        return self


class CleanedConversation(CleaningSchema):
    source_conversation_id: NonEmptyString
    platform: NonEmptyString
    title: str | None = None
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    time_range_derived: bool = False
    participants: list[CanonicalParticipant] = Field(default_factory=list)
    cleaned_messages: list[CleanedMessage] = Field(default_factory=list)
    analysis_units: list[AnalysisUnit] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CleaningStatistics(CleaningSchema):
    conversation_count: NonNegativeInt
    input_message_count: NonNegativeInt
    output_message_count: NonNegativeInt
    normalized_message_count: NonNegativeInt
    system_message_count: NonNegativeInt
    recalled_message_count: NonNegativeInt
    duplicate_message_count: NonNegativeInt
    excluded_message_count: NonNegativeInt
    redacted_message_count: NonNegativeInt
    redaction_count: NonNegativeInt
    url_replacement_count: NonNegativeInt
    attachment_placeholder_count: NonNegativeInt
    analysis_unit_count: NonNegativeInt
    warning_count: NonNegativeInt
    per_cleaner_counts: dict[str, NonNegativeInt] = Field(default_factory=dict)


class CleanedChatFile(CleaningSchema):
    source_filename: NonEmptyString
    file_hash: Sha256String
    parser_name: NonEmptyString
    parser_version: NonEmptyString
    cleaning_pipeline_version: NonEmptyString
    conversations: list[CleanedConversation] = Field(min_length=1)
    parser_warnings: list[ParseWarning] = Field(default_factory=list)
    cleaning_warnings: list[CleaningWarning] = Field(default_factory=list)
    statistics: CleaningStatistics

    @field_validator("source_filename")
    @classmethod
    def source_filename_must_not_be_a_path(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("source_filename must be a safe display name")
        return value

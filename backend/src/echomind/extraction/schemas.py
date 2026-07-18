"""Provider candidate output and safe extraction report schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from echomind.models.enums import InsightType

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExtractionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InsightCategory(StrEnum):
    BACKGROUND = "background"
    PREFERENCE = "preference"
    THINKING_PATTERN = "thinking_pattern"
    BEHAVIOR_EXECUTION = "behavior_execution"
    EMOTIONAL_RESPONSE = "emotional_response"
    RELATIONSHIP_PATTERN = "relationship_pattern"
    VALUES_MOTIVATION = "values_motivation"
    INTERNAL_CONFLICT = "internal_conflict"
    TEMPORAL_CHANGE = "temporal_change"
    OTHER = "other"


class CandidateEvidenceRole(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    CONTEXTUAL = "contextual"


class CandidateEvidenceRef(ExtractionSchema):
    context_message_id: Annotated[str, Field(pattern=r"^m[0-9]{3}$")]
    role: Annotated[CandidateEvidenceRole, Field(strict=False)]
    relevance_score: Annotated[float, Field(ge=0, le=1)]

    @field_validator("role", mode="before")
    @classmethod
    def parse_role(cls, value: object) -> object:
        return CandidateEvidenceRole(value) if isinstance(value, str) else value


class CandidateInsight(ExtractionSchema):
    insight_type: Annotated[InsightType, Field(strict=False)]
    category: Annotated[InsightCategory, Field(strict=False)]
    title: NonEmptyText = Field(max_length=255)
    statement: NonEmptyText = Field(max_length=2_000)
    evidence_refs: Annotated[list[CandidateEvidenceRef], Field(min_length=1, max_length=40)]
    model_confidence: Annotated[float, Field(ge=0, le=1)]
    explicit_self_report: bool
    reasoning_basis: str | None = Field(default=None, max_length=1_000)
    alternative_explanations: Annotated[list[str], Field(max_length=10)] = Field(
        default_factory=list
    )
    valid_from: Annotated[AwareDatetime, Field(strict=False)] | None = None
    valid_to: Annotated[AwareDatetime, Field(strict=False)] | None = None

    @field_validator("insight_type", mode="before")
    @classmethod
    def parse_insight_type(cls, value: object) -> object:
        return InsightType(value) if isinstance(value, str) else value

    @field_validator("category", mode="before")
    @classmethod
    def parse_category(cls, value: object) -> object:
        return InsightCategory(value) if isinstance(value, str) else value

    @field_validator("valid_from", "valid_to", mode="before")
    @classmethod
    def parse_iso_datetime(cls, value: object) -> object:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("candidate times must include a timezone")
            return parsed
        return value

    @field_validator("reasoning_basis")
    @classmethod
    def blank_reasoning_is_absent(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("reasoning_basis must not be blank")
        return value

    @field_validator("alternative_explanations")
    @classmethod
    def alternatives_are_bounded_and_unique(cls, values: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 500 for item in values):
            raise ValueError("alternative explanations must be non-empty and bounded")
        if len(values) != len(set(values)):
            raise ValueError("alternative explanations must be unique")
        return values

    @field_validator("evidence_refs")
    @classmethod
    def evidence_refs_are_unique(
        cls, values: list[CandidateEvidenceRef]
    ) -> list[CandidateEvidenceRef]:
        keys = [(item.context_message_id, item.role) for item in values]
        if len(keys) != len(set(keys)):
            raise ValueError("evidence references must be unique")
        return values

    @model_validator(mode="after")
    def time_range_is_valid(self) -> CandidateInsight:
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_to < self.valid_from:
                raise ValueError("valid_to must not be earlier than valid_from")
        return self


class CandidateInsightBatch(ExtractionSchema):
    candidates: Annotated[list[CandidateInsight], Field(max_length=50)] = Field(
        default_factory=list
    )


class ExtractionErrorRecord(ExtractionSchema):
    error_code: str
    message: str
    request_id: str
    window_id: str | None = None
    conversation_id: str | None = None
    recoverable: bool
    details: dict[str, str | int | bool] = Field(default_factory=dict)


class WindowResult(ExtractionSchema):
    window_id: str
    conversation_id: str
    message_count: int = Field(ge=0)
    truncated_message_count: int = Field(ge=0)
    provider_attempts: int = Field(ge=0)
    candidates_received: int = Field(ge=0)
    candidates_accepted: int = Field(ge=0)
    candidates_rejected: int = Field(ge=0)
    insights_created: int = Field(ge=0)
    insights_reused: int = Field(ge=0)
    error_code: str | None = None


class ExtractionReport(ExtractionSchema):
    request_id: UUID
    extraction_version: str
    provider_name: str
    model_name: str
    conversation_count: int = Field(ge=0)
    selected_message_count: int = Field(ge=0)
    excluded_message_count: int = Field(ge=0)
    truncated_message_count: int = Field(ge=0)
    window_count: int = Field(ge=0)
    successful_window_count: int = Field(ge=0)
    failed_window_count: int = Field(ge=0)
    candidates_received: int = Field(ge=0)
    candidates_accepted: int = Field(ge=0)
    candidates_rejected: int = Field(ge=0)
    insights_created: int = Field(ge=0)
    insights_reused: int = Field(ge=0)
    evidence_created: int = Field(ge=0)
    evidence_reused: int = Field(ge=0)
    links_created: int = Field(ge=0)
    links_reused: int = Field(ge=0)
    stopped_early: bool
    window_results: list[WindowResult] = Field(default_factory=list)
    errors: list[ExtractionErrorRecord] = Field(default_factory=list)

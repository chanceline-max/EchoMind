"""Insight and evidence-link schemas."""

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from echomind.models.enums import EvidenceState, InsightStatus, InsightType
from echomind.schemas.common import Confidence, NonEmptyString, ReadSchema, StrictSchema


class InsightCreate(StrictSchema):
    category: NonEmptyString = Field(max_length=100)
    insight_type: InsightType
    title: NonEmptyString = Field(max_length=255)
    statement: NonEmptyString
    confidence: Confidence
    status: InsightStatus = InsightStatus.PROPOSED
    evidence_state: EvidenceState = EvidenceState.VALID
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    model_name: str | None = Field(default=None, max_length=255)
    provider_name: str | None = Field(default=None, max_length=128)
    provider_request_id: str | None = Field(default=None, max_length=36)
    extraction_version: NonEmptyString = Field(max_length=100)
    insight_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_confidence: Confidence | None = None
    explicit_self_report: bool = False
    confidence_version: NonEmptyString = Field(default="unscored", max_length=100)
    confidence_input_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    confidence_factors_json: dict[str, Any] | None = None
    confidence_explanation: str | None = Field(default=None, max_length=4_000)
    confidence_as_of: AwareDatetime | None = None
    confidence_calculated_at: AwareDatetime | None = None
    reasoning_basis: str | None = None
    alternative_explanations: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time_range(self) -> "InsightCreate":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be earlier than valid_from")
        return self


class InsightRead(ReadSchema):
    id: UUID
    category: str
    insight_type: InsightType
    title: str
    statement: str
    confidence: float
    status: InsightStatus
    evidence_state: EvidenceState
    valid_from: AwareDatetime | None
    valid_to: AwareDatetime | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    model_name: str | None
    provider_name: str | None
    provider_request_id: str | None
    extraction_version: str
    insight_fingerprint: str | None
    model_confidence: float | None
    explicit_self_report: bool
    confidence_version: str
    confidence_input_fingerprint: str | None
    confidence_factors_json: dict[str, Any] | None
    confidence_explanation: str | None
    confidence_as_of: AwareDatetime | None
    confidence_calculated_at: AwareDatetime | None
    reasoning_basis: str | None
    alternative_explanations: list[str]
    metadata_json: dict[str, Any]


class InsightEvidenceCreate(StrictSchema):
    insight_id: UUID
    evidence_id: UUID


class InsightEvidenceRead(ReadSchema):
    insight_id: UUID
    evidence_id: UUID
    created_at: AwareDatetime

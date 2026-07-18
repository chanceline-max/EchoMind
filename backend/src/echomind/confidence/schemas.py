"""Strict, content-free confidence score and report contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from echomind.models.enums import EvidenceState

UnitFloat = Annotated[float, Field(ge=0, le=1)]


class ConfidenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MinimumRuleCode(StrEnum):
    PASSED = "passed"
    NOT_EVALUATED = "not_evaluated"
    EVIDENCE_INVALID = "evidence_invalid"
    FACT_SELF_REPORT_REQUIREMENT_FAILED = "fact_self_report_requirement_failed"
    PREFERENCE_SUPPORT_REQUIREMENT_FAILED = "preference_support_requirement_failed"
    PATTERN_EVIDENCE_REQUIREMENT_FAILED = "pattern_evidence_requirement_failed"
    PATTERN_TIME_REQUIREMENT_FAILED = "pattern_time_requirement_failed"
    INFERENCE_REASONING_REQUIREMENT_FAILED = "inference_reasoning_requirement_failed"
    INFERENCE_ALTERNATIVES_REQUIREMENT_FAILED = "inference_alternatives_requirement_failed"
    HYPOTHESIS_REASONING_REQUIREMENT_FAILED = "hypothesis_reasoning_requirement_failed"
    HYPOTHESIS_ALTERNATIVES_REQUIREMENT_FAILED = "hypothesis_alternatives_requirement_failed"
    CONTRADICTION_ROLES_INCOMPLETE = "contradiction_roles_incomplete"
    CHANGE_TIME_REQUIREMENT_FAILED = "change_time_requirement_failed"
    CHANGE_RANGE_REQUIREMENT_FAILED = "change_range_requirement_failed"


class ConfidenceFactors(ConfidenceSchema):
    explicitness: UnitFloat
    evidence_quantity: UnitFloat
    temporal_span: UnitFloat
    context_diversity: UnitFloat
    evidence_quality: UnitFloat
    recency: UnitFloat
    contradiction_factor: UnitFloat
    bilateral_balance: UnitFloat
    inference_depth_penalty: UnitFloat
    base_score: UnitFloat
    positive_contribution: UnitFloat
    contradiction_penalty: UnitFloat
    score_before_cap: UnitFloat
    type_cap: UnitFloat
    final_confidence: UnitFloat
    valid_ratio: UnitFloat
    owner_ratio: UnitFloat
    non_contextual_ratio: UnitFloat
    average_relevance: UnitFloat
    valid_evidence_count: int = Field(ge=0)
    invalid_evidence_count: int = Field(ge=0)
    owner_evidence_count: int = Field(ge=0)
    supporting_evidence_count: int = Field(ge=0)
    contradicting_evidence_count: int = Field(ge=0)
    contextual_evidence_count: int = Field(ge=0)
    unique_timestamp_count: int = Field(ge=0)
    unique_conversation_count: int = Field(ge=0)
    newest_evidence_at: AwareDatetime | None
    oldest_evidence_at: AwareDatetime | None
    as_of: AwareDatetime
    calculation_version: str
    model_confidence_ignored: bool = True


class ConfidenceScore(ConfidenceSchema):
    insight_id: str
    confidence_version: str
    confidence_input_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    evidence_state: EvidenceState
    factors: ConfidenceFactors
    explanation: Annotated[str, Field(min_length=1, max_length=4_000)]
    final_confidence: UnitFloat
    as_of: AwareDatetime
    calculated_at: AwareDatetime
    minimum_rule_passed: bool
    minimum_rule_code: MinimumRuleCode
    changed: bool = False


class ConfidenceErrorRecord(ConfidenceSchema):
    error_code: str
    message: str
    request_id: str
    insight_id: str | None = None
    recoverable: bool
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ConfidenceResult(ConfidenceSchema):
    insight_id: str
    status: str
    previous_confidence: float | None
    final_confidence: float | None
    evidence_state: EvidenceState | None
    changed: bool
    input_fingerprint_changed: bool
    minimum_rule_passed: bool
    minimum_rule_code: MinimumRuleCode
    error_code: str | None = None


class ConfidenceReport(ConfidenceSchema):
    request_id: UUID
    confidence_version: str
    as_of: AwareDatetime
    requested_count: int = Field(ge=0)
    found_count: int = Field(ge=0)
    scored_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)
    skipped_rejected_count: int = Field(ge=0)
    skipped_superseded_count: int = Field(ge=0)
    invalid_evidence_count: int = Field(ge=0)
    minimum_rule_failed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    stopped_early: bool
    results: list[ConfidenceResult] = Field(default_factory=list)
    errors: list[ConfidenceErrorRecord] = Field(default_factory=list)


def same_utc_instant(first: datetime | None, second: datetime) -> bool:
    return first is not None and first == second

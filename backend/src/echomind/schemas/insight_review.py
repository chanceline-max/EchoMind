"""Strict stage-nine Insight review API contracts."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from echomind.models.enums import (
    EvidenceInvalidationReason,
    EvidenceState,
    InsightRevisionAction,
    InsightStatus,
    InsightType,
    RevisionActorType,
)

Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
AllowedAction = Literal[
    "edit",
    "confirm",
    "reject",
    "restore_to_proposed",
    "restore_to_confirmed",
    "supersede",
]


class ReviewSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InsightSummary(ReviewSchema):
    id: str
    title: str
    statement_summary: str
    category: str
    insight_type: InsightType
    status: InsightStatus
    confidence: float
    confidence_version: str
    model_confidence: float | None
    evidence_state: EvidenceState
    evidence_count: int
    valid_evidence_count: int
    contradicting_evidence_count: int
    valid_from: datetime | None
    valid_to: datetime | None
    revision_number: int
    reviewed_at: datetime | None
    superseded_by_insight_id: str | None
    created_at: datetime
    updated_at: datetime


class InsightPage(ReviewSchema):
    items: list[InsightSummary]
    total: int
    limit: int
    offset: int


class EvidenceDetail(ReviewSchema):
    evidence_id: str
    evidence_type: str
    stance: str
    relevance_score: float
    is_valid: bool
    invalidation_reasons: list[EvidenceInvalidationReason]
    invalidated_at: datetime | None
    excerpt: str
    message_id: str
    conversation_id: str
    message_timestamp: datetime | None
    sender_role: Literal["PROFILE_OWNER", "OTHER"]
    message_excluded_from_analysis: bool
    message_link: str


class InsightDetail(InsightSummary):
    statement: str
    reasoning_basis: str | None
    alternative_explanations: list[str]
    explicit_self_report: bool
    extraction_version: str
    provider_name: str | None
    confidence_explanation: str | None
    confidence_factors: dict[str, Any] | None
    review_note: str | None
    evidence: list[EvidenceDetail]
    allowed_actions: list[AllowedAction]


class InsightEditRequest(ReviewSchema):
    expected_revision: int = Field(ge=0)
    title: NonEmpty | None = Field(default=None, max_length=255)
    statement: NonEmpty | None = Field(default=None, max_length=100_000)
    category: NonEmpty | None = Field(default=None, max_length=100)
    insight_type: InsightType | None = None
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    review_note: Trimmed | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_edit(self) -> "InsightEditRequest":
        editable = self.model_fields_set - {"expected_revision"}
        if not editable:
            raise ValueError("at least one editable field is required")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be earlier than valid_from")
        return self


class ReviewActionRequest(ReviewSchema):
    expected_revision: int = Field(ge=0)
    note: Trimmed | None = Field(default=None, max_length=2_000)


class RejectInsightRequest(ReviewSchema):
    expected_revision: int = Field(ge=0)
    note: NonEmpty = Field(min_length=3, max_length=2_000)


class RestoreInsightRequest(ReviewSchema):
    expected_revision: int = Field(ge=0)
    target_status: Literal[InsightStatus.PROPOSED, InsightStatus.CONFIRMED]
    note: Trimmed | None = Field(default=None, max_length=2_000)


class SupersedeInsightRequest(ReviewSchema):
    expected_revision: int = Field(ge=0)
    replacement_insight_id: NonEmpty = Field(max_length=36)
    note: Trimmed | None = Field(default=None, max_length=2_000)


class InsightRevisionRead(ReviewSchema):
    id: str
    insight_id: str
    revision_number: int
    action: InsightRevisionAction
    actor_type: RevisionActorType
    created_at: datetime
    expected_previous_revision: int
    changed_fields_json: dict[str, Any]
    snapshot_json: dict[str, Any]
    note: str | None


class InsightRevisionPage(ReviewSchema):
    items: list[InsightRevisionRead]
    total: int
    limit: int
    offset: int


class ReviewMutationResponse(ReviewSchema):
    insight: InsightDetail
    revision: InsightRevisionRead


class MessageLocation(ReviewSchema):
    message_id: str
    conversation_id: str
    zero_based_index: int
    suggested_offset: int

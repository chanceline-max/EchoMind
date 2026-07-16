"""Evidence input and read schemas."""

from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from echomind.models.enums import EvidenceStance
from echomind.schemas.common import (
    Confidence,
    NonEmptyString,
    NonNegativeInt,
    ReadSchema,
    Sha256String,
    StrictSchema,
)


class EvidenceCreate(StrictSchema):
    message_id: UUID
    excerpt: NonEmptyString
    excerpt_start: NonNegativeInt
    excerpt_end: NonNegativeInt
    excerpt_hash: Sha256String
    evidence_type: NonEmptyString = Field(max_length=100)
    stance: EvidenceStance = EvidenceStance.SUPPORTS
    relevance_score: Confidence
    is_valid: bool = True
    invalidated_at: AwareDatetime | None = None
    invalidation_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_evidence_state(self) -> "EvidenceCreate":
        if self.excerpt_end <= self.excerpt_start:
            raise ValueError("excerpt_end must be greater than excerpt_start")
        if not self.is_valid and self.invalidated_at is None:
            raise ValueError("invalid evidence must include invalidated_at")
        return self


class EvidenceRead(ReadSchema):
    id: UUID
    message_id: UUID
    excerpt: str
    excerpt_start: int
    excerpt_end: int
    excerpt_hash: str
    evidence_type: str
    stance: EvidenceStance
    relevance_score: float
    is_valid: bool
    invalidated_at: AwareDatetime | None
    invalidation_reason: str | None
    created_at: AwareDatetime

"""Bounded public contracts for synchronous user-triggered analysis."""

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from echomind.schemas.common import StrictSchema


class AnalysisRequest(StrictSchema):
    conversation_ids: Annotated[list[UUID], Field(min_length=1, max_length=100)]
    remote_consent: bool = False
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    stop_on_window_error: bool = True

    @field_validator("conversation_ids")
    @classmethod
    def stable_deduplicate_ids(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def time_range_is_valid(self) -> "AnalysisRequest":
        if self.start_at is not None and self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("end_at must not be earlier than start_at")
        return self


class AnalysisCapabilities(StrictSchema):
    configured_provider: str
    provider_available: bool
    remote_provider: bool
    remote_consent_required: bool
    extraction_version: str
    confidence_version: str
    max_conversations_per_request: int


class AnalysisErrorRecord(StrictSchema):
    error_code: str
    message: str
    recoverable: bool
    insight_id: str | None = None
    conversation_id: str | None = None
    window_id: str | None = None


class AnalysisResponse(StrictSchema):
    request_id: UUID
    provider_name: str
    conversation_count: int = Field(ge=0)
    selected_message_count: int = Field(ge=0)
    window_count: int = Field(ge=0)
    successful_window_count: int = Field(ge=0)
    failed_window_count: int = Field(ge=0)
    candidates_received: int = Field(ge=0)
    candidates_accepted: int = Field(ge=0)
    insights_created: int = Field(ge=0)
    insights_reused: int = Field(ge=0)
    insight_ids: list[str]
    confidence_scored_count: int = Field(ge=0)
    confidence_failed_count: int = Field(ge=0)
    stopped_early: bool
    errors: list[AnalysisErrorRecord]
    insights_link: str

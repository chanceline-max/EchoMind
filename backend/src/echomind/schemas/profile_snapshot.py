"""Profile snapshot input and read schemas."""

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from echomind.models.enums import EvidenceState
from echomind.schemas.common import NonEmptyString, ReadSchema, StrictSchema


class ProfileSnapshotCreate(StrictSchema):
    profile_version: NonEmptyString = Field(max_length=100)
    schema_version: NonEmptyString = Field(max_length=100)
    markdown_content: str
    json_content: dict[str, Any]
    source_range_start: AwareDatetime | None = None
    source_range_end: AwareDatetime | None = None
    statistics: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    evidence_state: EvidenceState = EvidenceState.VALID
    invalidated_at: AwareDatetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_profile_state(self) -> "ProfileSnapshotCreate":
        if (
            self.source_range_start
            and self.source_range_end
            and self.source_range_end < self.source_range_start
        ):
            raise ValueError("source_range_end must not be earlier than source_range_start")
        if self.evidence_state is EvidenceState.INVALID and self.invalidated_at is None:
            raise ValueError("invalid profile must include invalidated_at")
        return self


class ProfileSnapshotRead(ReadSchema):
    id: UUID
    generated_at: AwareDatetime
    profile_version: str
    schema_version: str
    markdown_content: str
    json_content: dict[str, Any]
    source_range_start: AwareDatetime | None
    source_range_end: AwareDatetime | None
    statistics: dict[str, Any]
    limitations: list[str]
    evidence_state: EvidenceState
    invalidated_at: AwareDatetime | None
    metadata_json: dict[str, Any]

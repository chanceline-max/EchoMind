"""Strict generation options for an immutable EchoProfile snapshot."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

PROFILE_VERSION = "echo-profile-1.0"
PROFILE_SCHEMA_VERSION = "echo-profile-document-1.0"
ProfileScope = Literal["all_confirmed", "selected_confirmed"]
EvidenceMode = Literal["references", "excerpts"]


class ProfileGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    profile_version: Literal["echo-profile-1.0"] = "echo-profile-1.0"
    profile_schema_version: Literal["echo-profile-document-1.0"] = "echo-profile-document-1.0"
    scope: ProfileScope = "all_confirmed"
    selected_insight_ids: list[UUID] = Field(default_factory=list, max_length=1_000)
    include_partial_evidence: bool = True
    include_invalidated: bool = True
    evidence_mode: EvidenceMode = "references"
    include_reasoning: bool = True
    generated_as_of: AwareDatetime

    @field_validator("selected_insight_ids")
    @classmethod
    def stable_unique_ids(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))

    @field_validator("generated_as_of")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_scope(self) -> "ProfileGenerationRequest":
        if self.scope == "selected_confirmed" and not self.selected_insight_ids:
            raise ValueError("selected_confirmed requires at least one selected_insight_id")
        if self.scope == "all_confirmed" and self.selected_insight_ids:
            raise ValueError("all_confirmed does not accept selected_insight_ids")
        return self

    def safe_options(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "selected_insight_ids": [str(value) for value in self.selected_insight_ids],
            "include_partial_evidence": self.include_partial_evidence,
            "include_invalidated": self.include_invalidated,
            "evidence_mode": self.evidence_mode,
            "include_reasoning": self.include_reasoning,
            "generated_as_of": self.generated_as_of.isoformat().replace("+00:00", "Z"),
        }

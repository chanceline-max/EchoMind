"""The sole structured source for EchoProfile Markdown and JSON."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from echomind.models.enums import EvidenceState, InsightType
from echomind.profiling.options import EvidenceMode, ProfileScope


class ProfileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileEvidenceItem(ProfileSchema):
    profile_evidence_ref: str = Field(pattern=r"^E\d{3,}$")
    evidence_id: str
    message_id: str
    conversation_id: str
    evidence_type: str
    role: Literal["supports", "contradicts", "context"]
    relevance_score: float = Field(ge=0, le=1)
    is_valid: bool
    invalidation_reasons: list[str]
    message_timestamp: AwareDatetime | None
    sender_role: Literal["PROFILE_OWNER", "OTHER"]
    excerpt: str | None = None


class ProfileInsightItem(ProfileSchema):
    profile_insight_ref: str = Field(pattern=r"^I\d{3,}$")
    insight_id: str
    insight_revision_number: int = Field(ge=0)
    insight_type: InsightType
    category: str
    title: str
    statement: str
    confidence: float = Field(ge=0, le=1)
    confidence_version: str
    confidence_explanation: str
    evidence_state: EvidenceState
    explicit_self_report: bool
    valid_from: AwareDatetime | None
    valid_to: AwareDatetime | None
    reasoning_basis: str | None
    alternative_explanations: list[str]
    evidence_refs: list[str]
    warnings: list[str]
    minimum_rule_code: str | None
    source_status_at_generation: Literal["current"] = "current"
    valid_evidence_count: int = Field(ge=0)
    invalid_evidence_count: int = Field(ge=0)


class ProfileSection(ProfileSchema):
    section_key: str
    title: str
    description: str
    items: list[ProfileInsightItem]


class ProfileSourceManifest(ProfileSchema):
    insight_id: str
    revision_number: int = Field(ge=0)
    status: str
    evidence_state: str
    confidence: float
    confidence_version: str
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_fingerprints: list[str]
    evidence_validity: list[bool]
    source_fingerprint_component: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProfileDocumentMetadata(ProfileSchema):
    profile_id: str
    profile_version: str
    schema_version: str
    generated_at: AwareDatetime
    generated_as_of: AwareDatetime
    selection_policy: Literal["confirmed-only-1.0"]
    scope: ProfileScope
    evidence_mode: EvidenceMode
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    generation_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_hash: str = Field(pattern=r"^$|^[0-9a-f]{64}$")
    confirmed_insight_count: int = Field(ge=0)
    included_valid_count: int = Field(ge=0)
    included_partial_count: int = Field(ge=0)
    invalidated_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    conversation_count: int = Field(ge=0)
    source_file_count: int = Field(ge=0)
    limitations: list[str]


class EchoProfileDocument(ProfileSchema):
    metadata: ProfileDocumentMetadata
    sections: list[ProfileSection]
    evidence_index: list[ProfileEvidenceItem]


class StalenessResult(ProfileSchema):
    current_source_status: Literal["current", "stale", "source_unavailable"]
    stale_reason_codes: list[str]


class BuiltProfile(ProfileSchema):
    document: EchoProfileDocument
    markdown_content: str
    json_content: str
    source_manifest: list[ProfileSourceManifest]
    generation_options: dict[str, object]


def utc_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")

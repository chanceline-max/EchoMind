"""The sole structured source for EchoProfile Markdown and JSON."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from echomind.models.enums import EvidenceState, InsightType
from echomind.profiling.options import EvidenceMode, ProfileScope


class ProfileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


PersonalityTendency = Literal[
    "low",
    "moderately_low",
    "balanced",
    "moderately_high",
    "high",
    "insufficient",
]
AssessmentConfidence = Literal["low", "medium", "high", "insufficient"]
FrameworkKey = Literal["big_five", "mbti"]
DimensionKey = Literal[
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "emotional_stability",
    "energy",
    "information",
    "decisions",
    "lifestyle",
]


class PersonalityDimension(ProfileSchema):
    dimension_key: DimensionKey
    label: str = Field(min_length=1, max_length=80)
    tendency: PersonalityTendency
    summary: str = Field(min_length=1, max_length=800)


class PersonalityFrameworkAssessment(ProfileSchema):
    framework: FrameworkKey
    display_name: str = Field(min_length=1, max_length=80)
    result: str = Field(min_length=1, max_length=120)
    confidence: AssessmentConfidence
    summary: str = Field(min_length=1, max_length=1_500)
    dimensions: list[PersonalityDimension] = Field(min_length=4, max_length=5)
    caveats: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "PersonalityFrameworkAssessment":
        expected = (
            {
                "openness",
                "conscientiousness",
                "extraversion",
                "agreeableness",
                "emotional_stability",
            }
            if self.framework == "big_five"
            else {"energy", "information", "decisions", "lifestyle"}
        )
        actual = {item.dimension_key for item in self.dimensions}
        if actual != expected or len(actual) != len(self.dimensions):
            raise ValueError("framework dimensions must match the selected framework")
        return self


class PersonalitySynthesis(ProfileSchema):
    synthesis_version: Literal["personality-synthesis-1.0"] = "personality-synthesis-1.0"
    headline: str = Field(min_length=1, max_length=120)
    overall_summary: str = Field(min_length=1, max_length=4_000)
    core_traits: list[str] = Field(min_length=3, max_length=8)
    thinking_style: str = Field(min_length=1, max_length=2_000)
    decision_style: str = Field(min_length=1, max_length=2_000)
    motivation_and_values: str = Field(min_length=1, max_length=2_000)
    social_and_relationship_style: str = Field(min_length=1, max_length=2_000)
    emotional_and_stress_patterns: str = Field(min_length=1, max_length=2_000)
    strengths: list[str] = Field(min_length=2, max_length=8)
    growth_edges: list[str] = Field(min_length=2, max_length=8)
    tensions_and_changes: list[str] = Field(max_length=8)
    framework_assessments: list[PersonalityFrameworkAssessment] = Field(
        min_length=2,
        max_length=2,
    )
    uncertainty_note: str = Field(min_length=1, max_length=1_500)
    provider_name: str = Field(min_length=1, max_length=128)
    model_name: str = Field(min_length=1, max_length=256)
    input_insight_count: int = Field(ge=1)
    omitted_insight_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_frameworks(self) -> "PersonalitySynthesis":
        frameworks = [item.framework for item in self.framework_assessments]
        if frameworks != ["big_five", "mbti"]:
            raise ValueError("framework assessments must contain Big Five followed by MBTI")
        return self


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
    personality_synthesis: PersonalitySynthesis | None = None
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

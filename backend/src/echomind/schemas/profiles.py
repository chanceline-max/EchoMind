"""HTTP contracts for immutable EchoProfile snapshots."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from echomind.profiling.options import EvidenceMode, ProfileGenerationRequest
from echomind.profiling.schemas import EchoProfileDocument


class ProfileApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProfileLinks(ProfileApiSchema):
    self: str
    markdown: str
    json_url: str = Field(serialization_alias="json")


class ProfileGenerationResponse(ProfileApiSchema):
    profile_snapshot_id: str
    profile_version: str
    schema_version: str
    generated_at: datetime
    source_fingerprint: str
    generation_fingerprint: str
    document_hash: str
    insight_count: int
    evidence_count: int
    source_status: Literal["current"]
    created: bool
    reused: bool
    links: ProfileLinks


class ProfileSummary(ProfileApiSchema):
    id: str
    generated_at: datetime
    profile_version: str
    schema_version: str
    insight_count: int
    evidence_count: int
    evidence_mode: EvidenceMode
    document_hash: str
    current_source_status: Literal["current", "stale", "source_unavailable"]
    stale_reason_codes: list[str]


class ProfilePage(ProfileApiSchema):
    items: list[ProfileSummary]
    total: int
    limit: int
    offset: int


class ProfileDetail(ProfileApiSchema):
    id: str
    generated_at: datetime
    profile_version: str
    schema_version: str
    insight_count: int
    evidence_count: int
    evidence_mode: EvidenceMode
    document_hash: str
    current_source_status: Literal["current", "stale", "source_unavailable"]
    stale_reason_codes: list[str]
    document: EchoProfileDocument
    links: ProfileLinks


__all__ = [
    "ProfileDetail",
    "ProfileGenerationRequest",
    "ProfileGenerationResponse",
    "ProfileLinks",
    "ProfilePage",
    "ProfileSummary",
]

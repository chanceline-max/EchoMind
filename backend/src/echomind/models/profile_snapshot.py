"""Immutable rendered profile snapshot storage."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Enum, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid, utc_now
from echomind.models.enums import EvidenceState, enum_values


class ProfileSnapshot(Base):
    """A versioned output artifact; generation remains outside stage two."""

    __tablename__ = "profile_snapshots"
    __table_args__ = (
        CheckConstraint("length(trim(profile_version)) > 0", name="profile_version_not_empty"),
        CheckConstraint("length(trim(schema_version)) > 0", name="schema_version_not_empty"),
        CheckConstraint(
            "source_range_end IS NULL OR source_range_start IS NULL "
            "OR source_range_end >= source_range_start",
            name="source_range_valid",
        ),
        CheckConstraint(
            "evidence_state != 'invalid' OR invalidated_at IS NOT NULL",
            name="invalid_profile_has_timestamp",
        ),
        CheckConstraint(
            "source_fingerprint IS NULL OR length(source_fingerprint) = 64",
            name="source_fingerprint_sha256_length",
        ),
        CheckConstraint(
            "generation_fingerprint IS NULL OR length(generation_fingerprint) = 64",
            name="generation_fingerprint_sha256_length",
        ),
        CheckConstraint(
            "document_hash IS NULL OR length(document_hash) = 64",
            name="document_hash_sha256_length",
        ),
        CheckConstraint(
            "insight_count IS NULL OR insight_count >= 0", name="insight_count_non_negative"
        ),
        CheckConstraint(
            "evidence_count IS NULL OR evidence_count >= 0", name="evidence_count_non_negative"
        ),
        CheckConstraint(
            "source_status_at_generation IS NULL OR source_status_at_generation = 'current'",
            name="source_status_at_generation_current",
        ),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    generated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        index=True,
    )
    profile_version: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    json_content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_range_start: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source_range_end: Mapped[datetime | None] = mapped_column(UTCDateTime())
    statistics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence_state: Mapped[EvidenceState] = mapped_column(
        Enum(
            EvidenceState,
            name="profile_evidence_state",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=EvidenceState.VALID,
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    source_fingerprint: Mapped[str | None] = mapped_column(String(64))
    generation_fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    document_hash: Mapped[str | None] = mapped_column(String(64))
    generation_options_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    source_manifest_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    insight_count: Mapped[int | None] = mapped_column(Integer)
    evidence_count: Mapped[int | None] = mapped_column(Integer)
    source_status_at_generation: Mapped[str | None] = mapped_column(String(32))


@event.listens_for(ProfileSnapshot, "before_update")
def _reject_profile_snapshot_update(*_: object) -> None:
    raise ValueError("ProfileSnapshot is immutable")


@event.listens_for(ProfileSnapshot, "before_delete")
def _reject_profile_snapshot_delete(*_: object) -> None:
    raise ValueError("ProfileSnapshot is immutable")

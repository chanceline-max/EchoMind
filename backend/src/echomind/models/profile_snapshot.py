"""Immutable rendered profile snapshot storage."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Enum, String, Text
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

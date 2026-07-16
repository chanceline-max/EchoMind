"""Uncertain insight model and its explicit evidence links."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid, utc_now
from echomind.models.enums import (
    EvidenceState,
    InsightStatus,
    InsightType,
    enum_values,
)

if TYPE_CHECKING:
    from echomind.models.evidence import Evidence


class InsightEvidence(Base):
    """Auditable many-to-many link between an insight and evidence."""

    __tablename__ = "insight_evidence"

    insight_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("insights.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    evidence_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("evidence.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    insight: Mapped["Insight"] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship(back_populates="insight_links")


class Insight(Base):
    """A versioned claim that is never stored as an unquestioned fact."""

    __tablename__ = "insights"
    __table_args__ = (
        CheckConstraint("length(trim(category)) > 0", name="category_not_empty"),
        CheckConstraint("length(trim(title)) > 0", name="title_not_empty"),
        CheckConstraint("length(trim(statement)) > 0", name="statement_not_empty"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="valid_time_range",
        ),
        CheckConstraint(
            "length(trim(extraction_version)) > 0",
            name="extraction_version_not_empty",
        ),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    insight_type: Mapped[InsightType] = mapped_column(
        Enum(
            InsightType,
            name="insight_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    status: Mapped[InsightStatus] = mapped_column(
        Enum(
            InsightStatus,
            name="insight_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        index=True,
        default=InsightStatus.PROPOSED,
    )
    evidence_state: Mapped[EvidenceState] = mapped_column(
        Enum(
            EvidenceState,
            name="evidence_state",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=EvidenceState.VALID,
    )
    valid_from: Mapped[datetime | None] = mapped_column(UTCDateTime())
    valid_to: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    model_name: Mapped[str | None] = mapped_column(String(255))
    extraction_version: Mapped[str] = mapped_column(String(100), nullable=False)
    reasoning_basis: Mapped[str | None] = mapped_column(Text)
    alternative_explanations: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    evidence_links: Mapped[list[InsightEvidence]] = relationship(
        back_populates="insight",
        passive_deletes="all",
    )

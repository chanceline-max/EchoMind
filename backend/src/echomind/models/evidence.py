"""Message excerpt used as traceable evidence for an insight."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid, utc_now
from echomind.models.enums import EvidenceStance, enum_values

if TYPE_CHECKING:
    from echomind.models.insight import InsightEvidence
    from echomind.models.message import Message


class Evidence(Base):
    """A bounded excerpt that remains linked to its source message."""

    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("length(excerpt) > 0", name="excerpt_not_empty"),
        CheckConstraint("excerpt_start >= 0", name="excerpt_start_non_negative"),
        CheckConstraint("excerpt_end > excerpt_start", name="excerpt_range_valid"),
        CheckConstraint("length(excerpt_hash) = 64", name="excerpt_hash_sha256_length"),
        CheckConstraint("length(trim(evidence_type)) > 0", name="evidence_type_not_empty"),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="relevance_score_range",
        ),
        CheckConstraint(
            "is_valid = 1 OR invalidated_at IS NOT NULL",
            name="invalid_evidence_has_timestamp",
        ),
        CheckConstraint(
            "evidence_fingerprint IS NULL OR length(evidence_fingerprint) = 64",
            name="evidence_fingerprint_sha256_length",
        ),
        Index(
            "ux_evidence_evidence_fingerprint",
            "evidence_fingerprint",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    message_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("messages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt_start: Mapped[int] = mapped_column(Integer, nullable=False)
    excerpt_end: Mapped[int] = mapped_column(Integer, nullable=False)
    excerpt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    stance: Mapped[EvidenceStance] = mapped_column(
        Enum(
            EvidenceStance,
            name="evidence_stance",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=EvidenceStance.SUPPORTS,
    )
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    invalidation_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    evidence_fingerprint: Mapped[str | None] = mapped_column(String(64))

    message: Mapped["Message"] = relationship(back_populates="evidences")
    insight_links: Mapped[list["InsightEvidence"]] = relationship(
        back_populates="evidence",
        passive_deletes="all",
    )

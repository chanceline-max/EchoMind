"""Append-only audit record for user-visible Insight review changes."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid, utc_now
from echomind.models.enums import InsightRevisionAction, RevisionActorType, enum_values

if TYPE_CHECKING:
    from echomind.models.insight import Insight


class InsightRevision(Base):
    """A revision can be inserted and read, but never edited or deleted by the ORM."""

    __tablename__ = "insight_revisions"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="revision_number_positive"),
        CheckConstraint(
            "expected_previous_revision >= 0",
            name="expected_previous_revision_non_negative",
        ),
        CheckConstraint("note IS NULL OR length(note) <= 2000", name="note_length"),
        UniqueConstraint(
            "insight_id",
            "revision_number",
            name="uq_insight_revisions_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    insight_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("insights.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[InsightRevisionAction] = mapped_column(
        Enum(
            InsightRevisionAction,
            name="insight_revision_action",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    actor_type: Mapped[RevisionActorType] = mapped_column(
        Enum(
            RevisionActorType,
            name="revision_actor_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    expected_previous_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_fields_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    insight: Mapped["Insight"] = relationship(back_populates="revisions")


@event.listens_for(InsightRevision, "before_update")
def _prevent_revision_update(*_: object) -> None:
    raise ValueError("InsightRevision records are append-only")


@event.listens_for(InsightRevision, "before_delete")
def _prevent_revision_delete(*_: object) -> None:
    raise ValueError("InsightRevision records are append-only")

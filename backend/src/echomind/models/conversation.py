"""Conversation model and participant association table."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid

if TYPE_CHECKING:
    from echomind.models.message import Message
    from echomind.models.participant import Participant
    from echomind.models.source_file import SourceFile

conversation_participants = Table(
    "conversation_participants",
    Base.metadata,
    Column(
        "conversation_id",
        String(UUID_LENGTH),
        ForeignKey("conversations.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "participant_id",
        String(UUID_LENGTH),
        ForeignKey("participants.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class Conversation(Base):
    """A conversation traced to exactly one source file."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("length(trim(platform)) > 0", name="platform_not_empty"),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="time_range_valid",
        ),
        UniqueConstraint(
            "source_file_id",
            "source_conversation_id",
            name="uq_conversations_source_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    source_file_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("source_files.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    source_conversation_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    source_file: Mapped["SourceFile"] = relationship(back_populates="conversations")
    participants: Mapped[list["Participant"]] = relationship(
        secondary=conversation_participants,
        back_populates="conversations",
        viewonly=True,
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        passive_deletes="all",
    )

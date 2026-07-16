"""Immutable raw and independently normalized message model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid, utc_now
from echomind.models.enums import MessageType, enum_values

if TYPE_CHECKING:
    from echomind.models.conversation import Conversation
    from echomind.models.evidence import Evidence
    from echomind.models.participant import Participant


class Message(Base):
    """One source message with raw content preserved independently."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("length(trim(source_message_id)) > 0", name="source_id_not_empty"),
        CheckConstraint("sequence_index >= 0", name="sequence_index_non_negative"),
        CheckConstraint(
            "length(trim(normalization_version)) > 0",
            name="normalization_version_not_empty",
        ),
        UniqueConstraint(
            "conversation_id",
            "source_message_id",
            name="uq_messages_conversation_source_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("conversations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_id: Mapped[str] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("participants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(
            MessageType,
            name="message_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=MessageType.TEXT,
    )
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_message_id: Mapped[str | None] = mapped_column(
        String(UUID_LENGTH),
        ForeignKey("messages.id", ondelete="RESTRICT"),
        index=True,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    excluded_from_analysis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_reason: Mapped[str | None] = mapped_column(String(500))
    normalization_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="raw-v1",
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sender: Mapped["Participant"] = relationship(back_populates="messages")
    reply_to: Mapped["Message | None"] = relationship(
        remote_side="Message.id",
        foreign_keys=[reply_to_message_id],
        back_populates="replies",
    )
    replies: Mapped[list["Message"]] = relationship(
        foreign_keys=[reply_to_message_id],
        back_populates="reply_to",
        passive_deletes="all",
    )
    evidences: Mapped[list["Evidence"]] = relationship(
        back_populates="message",
        passive_deletes="all",
    )

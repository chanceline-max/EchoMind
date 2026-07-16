"""Conversation participant model."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomind.db.base import Base
from echomind.db.types import UUID_LENGTH, UTCDateTime, new_uuid, utc_now
from echomind.models.conversation import conversation_participants

if TYPE_CHECKING:
    from echomind.models.conversation import Conversation
    from echomind.models.message import Message


class Participant(Base):
    """A declared sender identity without automatic identity inference."""

    __tablename__ = "participants"
    __table_args__ = (
        CheckConstraint("length(trim(canonical_name)) > 0", name="canonical_name_not_empty"),
    )

    id: Mapped[str] = mapped_column(String(UUID_LENGTH), primary_key=True, default=new_uuid)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_profile_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        secondary=conversation_participants,
        back_populates="participants",
        viewonly=True,
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="sender",
        passive_deletes="all",
    )

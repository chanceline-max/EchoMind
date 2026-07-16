"""Message input and read schemas."""

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field

from echomind.models.enums import MessageType
from echomind.schemas.common import NonEmptyString, NonNegativeInt, ReadSchema, StrictSchema


class MessageCreate(StrictSchema):
    conversation_id: UUID
    source_message_id: NonEmptyString = Field(max_length=255)
    sender_id: UUID
    timestamp: AwareDatetime | None = None
    sequence_index: NonNegativeInt = 0
    message_type: MessageType = MessageType.TEXT
    raw_content: str
    normalized_content: str
    reply_to_message_id: UUID | None = None
    is_deleted: bool = False
    archived_at: AwareDatetime | None = None
    excluded_from_analysis: bool = False
    exclusion_reason: str | None = Field(default=None, max_length=500)
    normalization_version: NonEmptyString = Field(default="raw-v1", max_length=100)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MessageRead(ReadSchema):
    id: UUID
    conversation_id: UUID
    source_message_id: str
    sender_id: UUID
    timestamp: AwareDatetime | None
    sequence_index: int
    message_type: MessageType
    raw_content: str
    normalized_content: str
    reply_to_message_id: UUID | None
    is_deleted: bool
    archived_at: AwareDatetime | None
    excluded_from_analysis: bool
    exclusion_reason: str | None
    normalization_version: str
    metadata_json: dict[str, Any]
    created_at: AwareDatetime

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
    source_order: NonNegativeInt = 0
    source_location: str | None = Field(default=None, max_length=500)
    message_type: MessageType = MessageType.TEXT
    raw_content: str
    normalized_content: str
    reply_to_message_id: UUID | None = None
    duplicate_of_message_id: UUID | None = None
    is_deleted: bool = False
    is_system_message: bool = False
    is_recalled_message: bool = False
    archived_at: AwareDatetime | None = None
    excluded_from_analysis: bool = False
    exclusion_reason: str | None = Field(default=None, max_length=500)
    exclusion_reasons_json: list[str] = Field(default_factory=list)
    cleaning_operations_json: list[dict[str, Any]] = Field(default_factory=list)
    normalization_version: NonEmptyString = Field(default="raw-v1", max_length=100)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MessageRead(ReadSchema):
    id: UUID
    conversation_id: UUID
    source_message_id: str
    sender_id: UUID
    timestamp: AwareDatetime | None
    sequence_index: int
    source_order: int
    source_location: str | None
    message_type: MessageType
    raw_content: str
    normalized_content: str
    reply_to_message_id: UUID | None
    duplicate_of_message_id: UUID | None
    is_deleted: bool
    is_system_message: bool
    is_recalled_message: bool
    archived_at: AwareDatetime | None
    excluded_from_analysis: bool
    exclusion_reason: str | None
    exclusion_reasons_json: list[str]
    cleaning_operations_json: list[dict[str, Any]]
    normalization_version: str
    metadata_json: dict[str, Any]
    created_at: AwareDatetime

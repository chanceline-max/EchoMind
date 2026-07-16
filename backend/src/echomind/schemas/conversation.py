"""Conversation input and read schemas."""

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from echomind.schemas.common import NonEmptyString, ReadSchema, StrictSchema


class ConversationCreate(StrictSchema):
    source_file_id: UUID
    platform: NonEmptyString = Field(max_length=100)
    source_conversation_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=500)
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    archived_at: AwareDatetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time_range(self) -> "ConversationCreate":
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be earlier than started_at")
        return self


class ConversationRead(ReadSchema):
    id: UUID
    source_file_id: UUID
    platform: str
    source_conversation_id: str | None
    title: str | None
    started_at: AwareDatetime | None
    ended_at: AwareDatetime | None
    archived_at: AwareDatetime | None
    metadata_json: dict[str, Any]

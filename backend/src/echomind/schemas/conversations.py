"""Conversation query response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParticipantSummary(ApiSchema):
    id: str
    display_name: str
    aliases: list[str]
    is_profile_owner: bool


class ConversationSummary(ApiSchema):
    id: str
    source_file_id: str
    platform: str
    title: str | None
    started_at: datetime | None
    ended_at: datetime | None
    participant_count: int
    message_count: int
    excluded_message_count: int


class ConversationDetail(ConversationSummary):
    source_conversation_id: str | None
    participants: list[ParticipantSummary]


class ConversationPage(ApiSchema):
    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int

"""Database-independent Canonical Chat Schema."""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from echomind.parsers.errors import ErrorCode

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256String = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
NonNegativeInt = Annotated[int, Field(ge=0)]


class CanonicalSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    SYSTEM = "system"
    OTHER = "other"


class ParseWarning(CanonicalSchema):
    error_code: ErrorCode
    message: str
    location: str | None = None
    recoverable: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class ParseStatistics(CanonicalSchema):
    conversation_count: NonNegativeInt
    participant_count: NonNegativeInt
    message_count: NonNegativeInt
    accepted_record_count: NonNegativeInt
    skipped_record_count: NonNegativeInt
    warning_count: NonNegativeInt


class CanonicalParticipant(CanonicalSchema):
    source_participant_id: NonEmptyString | None = None
    display_name: NonEmptyString
    aliases: list[NonEmptyString] = Field(default_factory=list)
    is_profile_owner: bool | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("aliases")
    @classmethod
    def aliases_must_be_unique(cls, aliases: list[str]) -> list[str]:
        if len(aliases) != len(set(aliases)):
            raise ValueError("aliases must be unique")
        return aliases


class CanonicalMessage(CanonicalSchema):
    source_message_id: NonEmptyString
    sender_source_id: NonEmptyString
    timestamp: AwareDatetime
    message_type: MessageType
    raw_content: str
    normalized_content: str
    reply_to_source_message_id: NonEmptyString | None = None
    source_order: NonNegativeInt
    source_location: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content_preservation(self) -> "CanonicalMessage":
        if self.normalized_content != self.raw_content:
            raise ValueError("Parser normalized_content must equal raw_content")
        if self.message_type is MessageType.TEXT and not self.raw_content.strip():
            raise ValueError("text messages require non-empty content")
        return self


class CanonicalConversation(CanonicalSchema):
    source_conversation_id: NonEmptyString
    platform: NonEmptyString
    title: str | None = None
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    time_range_derived: bool = False
    participants: list[CanonicalParticipant] = Field(default_factory=list)
    messages: list[CanonicalMessage] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_time_range(self) -> "CanonicalConversation":
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at must not be earlier than started_at")
        return self


class ParsedChatFile(CanonicalSchema):
    source_filename: NonEmptyString
    file_hash: Sha256String
    parser_name: NonEmptyString
    parser_version: NonEmptyString
    conversations: list[CanonicalConversation] = Field(min_length=1)
    warnings: list[ParseWarning] = Field(default_factory=list)
    statistics: ParseStatistics

    @field_validator("source_filename")
    @classmethod
    def source_filename_must_not_be_a_path(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("source_filename must be a safe display name")
        return value

    @model_validator(mode="after")
    def validate_statistics(self) -> "ParsedChatFile":
        conversation_count = len(self.conversations)
        participant_count = sum(len(item.participants) for item in self.conversations)
        message_count = sum(len(item.messages) for item in self.conversations)
        if (
            self.statistics.conversation_count != conversation_count
            or self.statistics.participant_count != participant_count
            or self.statistics.message_count != message_count
            or self.statistics.accepted_record_count != message_count
            or self.statistics.warning_count != len(self.warnings)
        ):
            raise ValueError("statistics do not match canonical data")
        return self

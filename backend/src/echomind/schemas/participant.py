"""Participant input and read schemas."""

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field

from echomind.schemas.common import NonEmptyString, ReadSchema, StrictSchema


class ParticipantCreate(StrictSchema):
    canonical_name: NonEmptyString = Field(max_length=255)
    aliases: list[str] = Field(default_factory=list)
    is_profile_owner: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class ParticipantRead(ReadSchema):
    id: UUID
    canonical_name: str
    aliases: list[str]
    is_profile_owner: bool
    created_at: AwareDatetime
    metadata_json: dict[str, Any]

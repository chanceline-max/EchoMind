"""Source-file input and read schemas."""

from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator

from echomind.models.enums import FileType, SourceFileStatus
from echomind.schemas.common import (
    NonEmptyString,
    NonNegativeInt,
    ReadSchema,
    Sha256String,
    StrictSchema,
)


class SourceFileCreate(StrictSchema):
    """Metadata accepted after a future importer has hashed a local file."""

    filename: NonEmptyString = Field(max_length=255)
    file_type: FileType
    file_hash: Sha256String
    byte_size: NonNegativeInt = 0
    imported_at: AwareDatetime | None = None
    parser_name: NonEmptyString = Field(max_length=100)
    parser_version: NonEmptyString = Field(max_length=100)
    status: SourceFileStatus = SourceFileStatus.PENDING
    archived_at: AwareDatetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("filename")
    @classmethod
    def filename_must_be_a_name(cls, value: str) -> str:
        """Do not accept a local path through the public schema."""

        if "/" in value or "\\" in value:
            raise ValueError("filename must not contain a path")
        return value


class SourceFileRead(ReadSchema):
    """Safe source-file output; storage_path is deliberately absent."""

    id: UUID
    filename: str
    file_type: FileType
    file_hash: str
    byte_size: int
    imported_at: AwareDatetime
    parser_name: str
    parser_version: str
    status: SourceFileStatus
    archived_at: AwareDatetime | None
    metadata_json: dict[str, Any]

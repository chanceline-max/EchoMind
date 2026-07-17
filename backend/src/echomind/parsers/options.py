"""Explicit parser behavior options."""

import codecs
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator


class ErrorMode(StrEnum):
    STRICT = "strict"
    LENIENT = "lenient"


class ParserOptions(BaseModel):
    """Options that must never depend on host locale or timezone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_mode: ErrorMode = ErrorMode.STRICT
    default_timezone: str | None = None
    encoding: str = "utf-8"

    @field_validator("default_timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ValueError("default_timezone must be a valid IANA timezone") from error
        return value

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, value: str) -> str:
        try:
            return codecs.lookup(value).name
        except LookupError as error:
            raise ValueError("encoding must be supported by the Python standard library") from error

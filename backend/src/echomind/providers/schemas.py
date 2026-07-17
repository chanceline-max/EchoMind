"""Strict request, usage, and result schemas owned by EchoMind."""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_FORBIDDEN_METADATA_KEYS = {
    "api_key",
    "authorization",
    "content",
    "database_url",
    "endpoint",
    "password",
    "prompt",
    "raw_content",
    "response",
    "secret",
    "system_instruction",
    "user_content",
}


class ProviderSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LLMContent(ProviderSchema):
    """One caller-supplied user message; assistant and tool history are out of scope."""

    role: Literal["user"] = "user"
    content: Annotated[str, Field(min_length=1, max_length=1_000_000)]

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class LLMRequest(ProviderSchema):
    request_id: UUID = Field(default_factory=uuid4)
    system_instruction: Annotated[str, Field(min_length=1, max_length=100_000)]
    user_content: Annotated[list[LLMContent], Field(min_length=1, max_length=10_000)]
    response_schema_name: Annotated[str, Field(min_length=1, max_length=128)]
    provider_name: Annotated[str, Field(min_length=1, max_length=128)]
    model_name: Annotated[str, Field(min_length=1, max_length=256)]
    temperature: Annotated[float, Field(ge=0, le=2)] = 0.0
    max_output_tokens: Annotated[int, Field(ge=1, le=1_000_000)] = 1_024
    timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 30.0
    metadata_json: dict[str, JsonValue] = Field(default_factory=dict)
    remote_consent: bool = False
    request_version: Annotated[str, Field(min_length=1, max_length=32)] = "1.0"

    @field_validator("system_instruction")
    @classmethod
    def reject_blank_instruction(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("system_instruction must not be blank")
        return value

    @field_validator("response_schema_name", "provider_name", "request_version")
    @classmethod
    def validate_safe_name(cls, value: str) -> str:
        if _SAFE_NAME.fullmatch(value) is None:
            raise ValueError("value must be a safe identifier")
        return value

    @field_validator("metadata_json")
    @classmethod
    def validate_safe_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if len(value) > 32:
            raise ValueError("metadata_json has too many fields")
        if len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) > 4_096:
            raise ValueError("metadata_json is too large")
        for key, item in value.items():
            normalized = key.casefold()
            if _SAFE_NAME.fullmatch(key) is None:
                raise ValueError("metadata_json contains an unsafe field name")
            if normalized in _FORBIDDEN_METADATA_KEYS or any(
                marker in normalized for marker in ("token", "credential")
            ):
                raise ValueError("metadata_json contains a forbidden field")
            _validate_metadata_value(item)
        return value


def _validate_metadata_value(value: JsonValue) -> None:
    if isinstance(value, str):
        lowered = value.casefold()
        if (
            len(value) > 256
            or "\n" in value
            or "\r" in value
            or "\\" in value
            or "://" in value
            or lowered.startswith(("/home/", "/users/", "bearer "))
        ):
            raise ValueError("metadata_json contains an unsafe string value")
    elif isinstance(value, list):
        for item in value:
            _validate_metadata_value(item)
    elif isinstance(value, dict):
        if len(value) > 32:
            raise ValueError("metadata_json contains an oversized object")
        for nested_key, item in value.items():
            if _SAFE_NAME.fullmatch(nested_key) is None:
                raise ValueError("metadata_json contains an unsafe nested field name")
            _validate_metadata_value(item)


class LLMUsage(ProviderSchema):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_input_characters: int = Field(ge=0)
    estimated_output_limit: int = Field(ge=1)


class LLMResult[ResultT: BaseModel](ProviderSchema):
    request_id: UUID
    provider_name: str
    provider_version: str
    model_name: str
    output: ResultT
    usage: LLMUsage
    finish_reason: str | None = None
    attempts: int = Field(ge=1)
    duration_ms: int = Field(ge=0)
    response_format: Literal["json_schema"] = "json_schema"
    request_version: str
    provider_metadata_json: dict[str, JsonValue] = Field(default_factory=dict)

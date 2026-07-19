"""Strict internal request and bounded window options for candidate extraction."""

from __future__ import annotations

from typing import Annotated, Final, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_EXTRACTION_VERSION: Final[Literal["candidate-extraction-1.1"]] = "candidate-extraction-1.1"
WINDOW_PARAMETERS_VERSION = "window-1.0"


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID = Field(default_factory=uuid4)
    conversation_ids: Annotated[
        list[Annotated[UUID, Field(strict=False)]],
        Field(min_length=1, max_length=100),
    ]
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    provider_name: Literal["mock", "openai_compatible", "local"] = "mock"
    model_name: Annotated[str, Field(min_length=1, max_length=256)] = "mock-model"
    remote_consent: bool = False
    extraction_version: Literal["candidate-extraction-1.1"] = DEFAULT_EXTRACTION_VERSION
    max_window_messages: Annotated[int, Field(ge=2, le=200)] = 40
    max_window_characters: Annotated[int, Field(ge=64, le=100_000)] = 12_000
    max_single_message_characters: Annotated[int, Field(ge=32, le=20_000)] = 4_000
    overlap_messages: Annotated[int, Field(ge=0, le=50)] = 4
    max_candidates_per_window: Annotated[int, Field(ge=1, le=50)] = 10
    stop_on_window_error: bool = True

    @field_validator("conversation_ids")
    @classmethod
    def stable_deduplicate_conversation_ids(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))

    @field_validator("model_name")
    @classmethod
    def model_name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("model_name must not be blank")
        return value

    @model_validator(mode="after")
    def ranges_and_windows_are_valid(self) -> ExtractionRequest:
        if self.start_at is not None and self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("end_at must not be earlier than start_at")
        if self.overlap_messages >= self.max_window_messages:
            raise ValueError("overlap_messages must be smaller than max_window_messages")
        if self.max_single_message_characters > self.max_window_characters:
            raise ValueError("max_single_message_characters must not exceed max_window_characters")
        return self

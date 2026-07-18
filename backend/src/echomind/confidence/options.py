"""Strict and bounded internal request for confidence recalculation."""

from datetime import UTC, datetime
from typing import Annotated, Final, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

CONFIDENCE_VERSION: Final[Literal["confidence-1.0"]] = "confidence-1.0"


class ConfidenceCalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: UUID = Field(default_factory=uuid4)
    insight_ids: Annotated[
        list[Annotated[UUID, Field(strict=False)]],
        Field(min_length=1, max_length=1_000),
    ]
    as_of: AwareDatetime
    confidence_version: Literal["confidence-1.0"] = CONFIDENCE_VERSION
    include_rejected: bool = False
    include_superseded: bool = False
    force_recalculate: bool = False
    stop_on_error: bool = True

    @field_validator("insight_ids")
    @classmethod
    def stable_deduplicate_ids(cls, values: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(values))

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

"""Shared validation primitives for database-facing schemas."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256String = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Confidence = Annotated[float, Field(ge=0, le=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class StrictSchema(BaseModel):
    """Reject unknown input instead of silently discarding it."""

    model_config = ConfigDict(extra="forbid")


class ReadSchema(BaseModel):
    """Read an ORM object without exposing undeclared database fields."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

"""Synchronous provider protocol for structured output only."""

from typing import ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel

from echomind.providers.schemas import LLMRequest, LLMResult, ResponseModelT


@runtime_checkable
class LLMProvider(Protocol):
    provider_name: ClassVar[str]
    provider_version: ClassVar[str]
    supports_remote_calls: ClassVar[bool]
    supports_structured_output: ClassVar[bool]

    def generate_structured(
        self,
        request: LLMRequest,
        response_schema: type[ResponseModelT],
    ) -> LLMResult[ResponseModelT]: ...


def is_response_model(value: object) -> bool:
    """Return whether a value is a Pydantic model class without instantiating it."""
    return isinstance(value, type) and issubclass(value, BaseModel)

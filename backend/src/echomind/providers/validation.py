"""Central endpoint, budget, and structured-output validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError

from echomind.providers.errors import ProviderError, ProviderErrorCode
from echomind.providers.schemas import LLMRequest, ResponseModelT

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
MAX_ENDPOINT_CHARACTERS = 2_048


@dataclass(frozen=True)
class BudgetLimits:
    max_input_characters: int
    max_messages: int
    max_message_characters: int
    max_schema_characters: int
    max_output_tokens: int


def validate_endpoint(endpoint: str, *, allow_insecure_local_http: bool) -> str:
    """Validate a server-owned endpoint and return its unchanged value."""
    if not endpoint or len(endpoint) > MAX_ENDPOINT_CHARACTERS:
        raise ValueError("endpoint length is invalid")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("endpoint must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("endpoint credentials are forbidden")
    if parsed.fragment:
        raise ValueError("endpoint fragments are forbidden")
    if parsed.scheme == "http" and (
        not allow_insecure_local_http or parsed.hostname.casefold() not in LOCAL_HOSTS
    ):
        raise ValueError("HTTP endpoints are restricted to explicitly enabled localhost")
    return endpoint


def schema_json(response_schema: type[BaseModel]) -> str:
    return json.dumps(
        response_schema.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def estimated_input_characters(request: LLMRequest) -> int:
    return len(request.system_instruction) + sum(len(item.content) for item in request.user_content)


def _budget_error(
    code: ProviderErrorCode,
    *,
    request: LLMRequest,
    limit_name: str,
    allowed: int,
    actual: int,
) -> ProviderError:
    return ProviderError(
        code,
        message="The provider request exceeds a configured safety budget.",
        provider_name=request.provider_name,
        request_id=str(request.request_id),
        details={"limit_name": limit_name, "allowed": allowed, "actual": actual},
    )


def validate_request_budget(
    request: LLMRequest,
    response_schema: type[BaseModel],
    limits: BudgetLimits,
) -> tuple[int, str]:
    """Fail before any transport call and return deterministic size metadata."""
    if (
        not isinstance(response_schema, type)
        or not issubclass(response_schema, BaseModel)
        or response_schema.model_config.get("extra") != "forbid"
    ):
        raise ProviderError(
            ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION,
            message="The response schema must be a strict Pydantic model that forbids extras.",
            provider_name=request.provider_name,
            request_id=str(request.request_id),
        )
    message_count = len(request.user_content)
    if message_count > limits.max_messages:
        raise _budget_error(
            ProviderErrorCode.INPUT_BUDGET_EXCEEDED,
            request=request,
            limit_name="message_count",
            allowed=limits.max_messages,
            actual=message_count,
        )
    for item in request.user_content:
        if len(item.content) > limits.max_message_characters:
            raise _budget_error(
                ProviderErrorCode.INPUT_BUDGET_EXCEEDED,
                request=request,
                limit_name="message_characters",
                allowed=limits.max_message_characters,
                actual=len(item.content),
            )
    input_characters = estimated_input_characters(request)
    if input_characters > limits.max_input_characters:
        raise _budget_error(
            ProviderErrorCode.INPUT_BUDGET_EXCEEDED,
            request=request,
            limit_name="input_characters",
            allowed=limits.max_input_characters,
            actual=input_characters,
        )
    try:
        serialized_schema = schema_json(response_schema)
    except Exception:
        raise ProviderError(
            ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION,
            message="The requested response schema could not be serialized safely.",
            provider_name=request.provider_name,
            request_id=str(request.request_id),
        ) from None
    if len(serialized_schema) > limits.max_schema_characters:
        raise _budget_error(
            ProviderErrorCode.SCHEMA_TOO_LARGE,
            request=request,
            limit_name="schema_characters",
            allowed=limits.max_schema_characters,
            actual=len(serialized_schema),
        )
    if request.max_output_tokens > limits.max_output_tokens:
        raise _budget_error(
            ProviderErrorCode.OUTPUT_BUDGET_EXCEEDED,
            request=request,
            limit_name="max_output_tokens",
            allowed=limits.max_output_tokens,
            actual=request.max_output_tokens,
        )
    return input_characters, serialized_schema


def parse_structured_output(
    content: str,
    *,
    response_schema: type[ResponseModelT],
    provider_name: str,
    request_id: str,
    attempts: int,
) -> ResponseModelT:
    """Require pure JSON and validate without exposing rejected values."""
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProviderError(
            ProviderErrorCode.INVALID_JSON_RESPONSE,
            message="The provider returned invalid JSON.",
            provider_name=provider_name,
            request_id=request_id,
            attempts=attempts,
        ) from None
    try:
        return response_schema.model_validate(parsed, strict=True)
    except ValidationError as error:
        safe_errors = error.errors(include_url=False, include_context=False, include_input=False)
        locations = [".".join(str(part) for part in item["loc"]) for item in safe_errors[:8]]
        raise ProviderError(
            ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED,
            message="The provider output does not match the requested schema.",
            provider_name=provider_name,
            request_id=request_id,
            attempts=attempts,
            details={
                "validation_error_count": len(safe_errors),
                "top_level_error_locations": locations,
            },
        ) from None
    except Exception:
        raise ProviderError(
            ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED,
            message="The provider output could not be validated safely.",
            provider_name=provider_name,
            request_id=request_id,
            attempts=attempts,
        ) from None

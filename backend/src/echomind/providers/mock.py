"""Deterministic offline provider used by default and in tests."""

from __future__ import annotations

import json
from typing import Any, ClassVar, Literal

from echomind.providers.errors import ProviderError, ProviderErrorCode
from echomind.providers.retry import Sleeper, backoff_seconds, default_sleeper
from echomind.providers.schemas import LLMRequest, LLMResult, LLMUsage, ResponseModelT
from echomind.providers.validation import (
    BudgetLimits,
    parse_structured_output,
    validate_request_budget,
)

MockScenario = Literal[
    "success",
    "invalid_json",
    "schema_mismatch",
    "transient_error_then_success",
    "timeout",
    "permanent_error",
    "empty_response",
    "retry_exhausted",
]


class MockLLMProvider:
    provider_name: ClassVar[str] = "mock"
    provider_version: ClassVar[str] = "1.0"
    supports_remote_calls: ClassVar[bool] = False
    supports_structured_output: ClassVar[bool] = True

    def __init__(
        self,
        *,
        response_payload: dict[str, Any] | None = None,
        scenario: MockScenario = "success",
        max_retries: int = 2,
        limits: BudgetLimits,
        sleeper: Sleeper = default_sleeper,
    ) -> None:
        self._response_payload = response_payload or {
            "summary": "Synthetic summary",
            "labels": ["synthetic"],
        }
        self._scenario = scenario
        self._max_retries = max_retries
        self._limits = limits
        self._sleeper = sleeper

    def generate_structured(
        self,
        request: LLMRequest,
        response_schema: type[ResponseModelT],
    ) -> LLMResult[ResponseModelT]:
        if request.provider_name != self.provider_name:
            raise ProviderError(
                ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION,
                message="The request provider does not match the mock provider.",
                provider_name=self.provider_name,
                request_id=str(request.request_id),
            )
        input_characters, _ = validate_request_budget(request, response_schema, self._limits)
        request_id = str(request.request_id)
        attempts = 0
        while True:
            attempts += 1
            try:
                content = self._content_for_attempt(attempts, request_id)
                output = parse_structured_output(
                    content,
                    response_schema=response_schema,
                    provider_name=self.provider_name,
                    request_id=request_id,
                    attempts=attempts,
                )
                return LLMResult[ResponseModelT](
                    request_id=request.request_id,
                    provider_name=self.provider_name,
                    provider_version=self.provider_version,
                    model_name=request.model_name,
                    output=output,
                    usage=LLMUsage(
                        input_tokens=None,
                        output_tokens=None,
                        total_tokens=None,
                        estimated_input_characters=input_characters,
                        estimated_output_limit=request.max_output_tokens,
                    ),
                    finish_reason="stop",
                    attempts=attempts,
                    duration_ms=0,
                    request_version=request.request_version,
                    provider_metadata_json={"scenario": self._scenario},
                )
            except ProviderError as error:
                if not error.recoverable:
                    raise
                if attempts > self._max_retries:
                    if self._max_retries == 0:
                        raise
                    raise ProviderError(
                        ProviderErrorCode.RETRY_EXHAUSTED,
                        message="The provider exhausted its configured retries.",
                        provider_name=self.provider_name,
                        request_id=request_id,
                        recoverable=False,
                        attempts=attempts,
                        details={"last_error_code": error.error_code.value},
                    ) from None
                self._sleeper(backoff_seconds(attempts))

    def _content_for_attempt(self, attempt: int, request_id: str) -> str:
        if self._scenario == "success":
            return json.dumps(self._response_payload, sort_keys=True, separators=(",", ":"))
        if self._scenario == "invalid_json":
            return "not-json"
        if self._scenario == "schema_mismatch":
            return "{}"
        if self._scenario == "empty_response":
            raise ProviderError(
                ProviderErrorCode.INVALID_UPSTREAM_RESPONSE,
                message="The mock provider returned an empty response.",
                provider_name=self.provider_name,
                request_id=request_id,
                attempts=attempt,
            )
        if self._scenario == "permanent_error":
            raise ProviderError(
                ProviderErrorCode.MOCK_SCENARIO_ERROR,
                message="The configured mock scenario failed permanently.",
                provider_name=self.provider_name,
                request_id=request_id,
                attempts=attempt,
            )
        if self._scenario == "transient_error_then_success" and attempt > 1:
            return json.dumps(self._response_payload, sort_keys=True, separators=(",", ":"))
        code = (
            ProviderErrorCode.TIMEOUT
            if self._scenario == "timeout"
            else ProviderErrorCode.CONNECTION_ERROR
        )
        raise ProviderError(
            code,
            message="The configured mock scenario failed transiently.",
            provider_name=self.provider_name,
            request_id=request_id,
            recoverable=True,
            attempts=attempt,
        )

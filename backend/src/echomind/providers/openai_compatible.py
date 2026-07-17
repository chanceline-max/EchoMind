"""OpenAI-compatible Chat Completions adapter with local strict validation."""

from __future__ import annotations

import json
from time import monotonic
from typing import Any, ClassVar, Never, cast

import httpx
from pydantic import SecretStr

from echomind.providers.errors import ProviderError, ProviderErrorCode
from echomind.providers.retry import Sleeper, backoff_seconds, default_sleeper
from echomind.providers.schemas import LLMRequest, LLMResult, LLMUsage, ResponseModelT
from echomind.providers.transport import HTTPTransport, HttpxTransport, TransportResponse
from echomind.providers.validation import (
    BudgetLimits,
    parse_structured_output,
    validate_endpoint,
    validate_request_budget,
)

RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class OpenAICompatibleProvider:
    provider_name: ClassVar[str] = "openai_compatible"
    provider_version: ClassVar[str] = "1.0"
    supports_remote_calls: ClassVar[bool] = True
    supports_structured_output: ClassVar[bool] = True

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: SecretStr,
        model_name: str,
        remote_enabled: bool,
        allow_insecure_local_http: bool,
        verify_tls: bool,
        request_timeout_seconds: float,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
        max_retries: int,
        max_response_bytes: int,
        limits: BudgetLimits,
        transport: HTTPTransport | None = None,
        sleeper: Sleeper = default_sleeper,
    ) -> None:
        try:
            self._endpoint = validate_endpoint(
                endpoint,
                allow_insecure_local_http=allow_insecure_local_http,
            )
        except ValueError:
            raise ProviderError(
                ProviderErrorCode.INVALID_ENDPOINT,
                message="The configured provider endpoint is not allowed.",
                provider_name=self.provider_name,
            ) from None
        if not api_key.get_secret_value().strip() or not model_name.strip():
            raise ProviderError(
                ProviderErrorCode.PROVIDER_NOT_CONFIGURED,
                message="The remote provider requires a model and API key.",
                provider_name=self.provider_name,
            )
        self._api_key = api_key
        self._model_name = model_name
        self._remote_enabled = remote_enabled
        self._verify_tls = verify_tls
        self._request_timeout_seconds = request_timeout_seconds
        self._connect_timeout_seconds = connect_timeout_seconds
        self._read_timeout_seconds = read_timeout_seconds
        self._max_retries = max_retries
        self._max_response_bytes = max_response_bytes
        self._limits = limits
        self._transport = transport or HttpxTransport()
        self._sleeper = sleeper

    def generate_structured(
        self,
        request: LLMRequest,
        response_schema: type[ResponseModelT],
    ) -> LLMResult[ResponseModelT]:
        request_id = str(request.request_id)
        if not self._remote_enabled:
            raise ProviderError(
                ProviderErrorCode.REMOTE_PROVIDER_DISABLED,
                message="Remote model calls are disabled by server configuration.",
                provider_name=self.provider_name,
                request_id=request_id,
            )
        if not request.remote_consent:
            raise ProviderError(
                ProviderErrorCode.REMOTE_CONSENT_REQUIRED,
                message="This remote model call requires explicit request consent.",
                provider_name=self.provider_name,
                request_id=request_id,
            )
        if request.provider_name != self.provider_name or request.model_name != self._model_name:
            raise ProviderError(
                ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION,
                message="The request provider or model does not match server configuration.",
                provider_name=self.provider_name,
                request_id=request_id,
            )

        input_characters, serialized_schema = validate_request_budget(
            request,
            response_schema,
            self._limits,
        )
        payload = self._build_payload(request, serialized_schema)
        started = monotonic()
        attempts = 0
        while True:
            attempts += 1
            try:
                effective_timeout = min(
                    request.timeout_seconds,
                    self._request_timeout_seconds,
                )
                response = self._transport.post_json(
                    url=self._endpoint,
                    payload=payload,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                    },
                    timeout_seconds=effective_timeout,
                    connect_timeout_seconds=min(
                        self._connect_timeout_seconds,
                        effective_timeout,
                    ),
                    read_timeout_seconds=min(
                        self._read_timeout_seconds,
                        effective_timeout,
                    ),
                    verify_tls=self._verify_tls,
                )
                self._raise_for_status(response, request_id=request_id, attempts=attempts)
                return self._parse_success(
                    response,
                    request=request,
                    response_schema=response_schema,
                    attempts=attempts,
                    input_characters=input_characters,
                    duration_ms=max(0, int((monotonic() - started) * 1_000)),
                )
            except ProviderError as error:
                if not error.recoverable:
                    raise
                if attempts > self._max_retries:
                    raise ProviderError(
                        ProviderErrorCode.RETRY_EXHAUSTED,
                        message="The provider exhausted its configured retries.",
                        provider_name=self.provider_name,
                        request_id=request_id,
                        attempts=attempts,
                        details={"last_error_code": error.error_code.value},
                    ) from None
                self._sleeper(backoff_seconds(attempts))
            except httpx.TimeoutException:
                timeout_error = ProviderError(
                    ProviderErrorCode.TIMEOUT,
                    message="The provider request timed out.",
                    provider_name=self.provider_name,
                    request_id=request_id,
                    recoverable=True,
                    attempts=attempts,
                )
                if attempts > self._max_retries:
                    if self._max_retries == 0:
                        raise timeout_error from None
                    raise ProviderError(
                        ProviderErrorCode.RETRY_EXHAUSTED,
                        message="The provider exhausted its configured retries.",
                        provider_name=self.provider_name,
                        request_id=request_id,
                        attempts=attempts,
                        details={"last_error_code": timeout_error.error_code.value},
                    ) from None
                self._sleeper(backoff_seconds(attempts))
            except httpx.TransportError:
                connection_error = ProviderError(
                    ProviderErrorCode.CONNECTION_ERROR,
                    message="The provider connection failed.",
                    provider_name=self.provider_name,
                    request_id=request_id,
                    recoverable=True,
                    attempts=attempts,
                )
                if attempts > self._max_retries:
                    if self._max_retries == 0:
                        raise connection_error from None
                    raise ProviderError(
                        ProviderErrorCode.RETRY_EXHAUSTED,
                        message="The provider exhausted its configured retries.",
                        provider_name=self.provider_name,
                        request_id=request_id,
                        attempts=attempts,
                        details={"last_error_code": connection_error.error_code.value},
                    ) from None
                self._sleeper(backoff_seconds(attempts))
            except Exception:
                raise ProviderError(
                    ProviderErrorCode.INVALID_UPSTREAM_RESPONSE,
                    message="The provider returned an unexpected response.",
                    provider_name=self.provider_name,
                    request_id=request_id,
                    attempts=attempts,
                ) from None

    def _build_payload(self, request: LLMRequest, serialized_schema: str) -> dict[str, Any]:
        schema_value = json.loads(serialized_schema)
        return {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": request.system_instruction},
                *[{"role": item.role, "content": item.content} for item in request.user_content],
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_schema_name,
                    "strict": True,
                    "schema": schema_value,
                },
            },
        }

    def _raise_for_status(
        self,
        response: TransportResponse,
        *,
        request_id: str,
        attempts: int,
    ) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if 300 <= status < 400:
            code = ProviderErrorCode.INVALID_UPSTREAM_RESPONSE
            message = "The provider redirect was refused."
            recoverable = False
        elif status in {401, 403}:
            code = ProviderErrorCode.UPSTREAM_AUTH_ERROR
            message = "The provider rejected its server-side credentials or permissions."
            recoverable = False
        elif status == 429:
            code = ProviderErrorCode.UPSTREAM_RATE_LIMITED
            message = "The provider rate limited the request."
            recoverable = True
        elif status in {408, 500, 502, 503, 504}:
            code = ProviderErrorCode.UPSTREAM_SERVER_ERROR
            message = "The provider reported a temporary upstream failure."
            recoverable = True
        elif 400 <= status < 500:
            code = ProviderErrorCode.UPSTREAM_CLIENT_ERROR
            message = "The provider rejected the request."
            recoverable = False
        else:
            code = ProviderErrorCode.UPSTREAM_SERVER_ERROR
            message = "The provider reported an upstream failure."
            recoverable = status in RETRYABLE_STATUS_CODES
        raise ProviderError(
            code,
            message=message,
            provider_name=self.provider_name,
            request_id=request_id,
            recoverable=recoverable,
            attempts=attempts,
            status_code=status,
        )

    def _parse_success(
        self,
        response: TransportResponse,
        *,
        request: LLMRequest,
        response_schema: type[ResponseModelT],
        attempts: int,
        input_characters: int,
        duration_ms: int,
    ) -> LLMResult[ResponseModelT]:
        request_id = str(request.request_id)
        if len(response.content) > self._max_response_bytes:
            raise ProviderError(
                ProviderErrorCode.RESPONSE_TOO_LARGE,
                message="The provider response exceeds the configured byte limit.",
                provider_name=self.provider_name,
                request_id=request_id,
                attempts=attempts,
                details={
                    "limit_name": "response_bytes",
                    "allowed": self._max_response_bytes,
                    "actual": len(response.content),
                },
            )
        try:
            envelope = json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError(
                ProviderErrorCode.INVALID_UPSTREAM_RESPONSE,
                message="The provider returned an invalid response envelope.",
                provider_name=self.provider_name,
                request_id=request_id,
                attempts=attempts,
                details={"received_content_type": response.headers.get("content-type", "unknown")},
            ) from None
        content, finish_reason = self._extract_content(
            envelope,
            request_id=request_id,
            attempts=attempts,
        )
        output = parse_structured_output(
            content,
            response_schema=response_schema,
            provider_name=self.provider_name,
            request_id=request_id,
            attempts=attempts,
        )
        usage_value = envelope.get("usage") if isinstance(envelope, dict) else None
        usage = usage_value if isinstance(usage_value, dict) else {}
        metadata: dict[str, Any] = {}
        if remote_request_id := response.headers.get("x-request-id"):
            metadata["remote_request_id"] = remote_request_id
        if api_version := response.headers.get("openai-version"):
            metadata["api_version"] = api_version
        return LLMResult[ResponseModelT](
            request_id=request.request_id,
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_name=self._model_name,
            output=output,
            usage=LLMUsage(
                input_tokens=_non_negative_int(usage.get("prompt_tokens")),
                output_tokens=_non_negative_int(usage.get("completion_tokens")),
                total_tokens=_non_negative_int(usage.get("total_tokens")),
                estimated_input_characters=input_characters,
                estimated_output_limit=request.max_output_tokens,
            ),
            finish_reason=finish_reason,
            attempts=attempts,
            duration_ms=duration_ms,
            request_version=request.request_version,
            provider_metadata_json=metadata,
        )

    def _extract_content(
        self,
        envelope: object,
        *,
        request_id: str,
        attempts: int,
    ) -> tuple[str, str | None]:
        if not isinstance(envelope, dict):
            self._invalid_envelope(request_id, attempts)
        envelope_dict = cast(dict[str, object], envelope)
        choices = envelope_dict.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            self._invalid_envelope(request_id, attempts)
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict):
            self._invalid_envelope(request_id, attempts)
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            self._invalid_envelope(request_id, attempts)
        finish_reason = choice.get("finish_reason")
        return content, finish_reason if isinstance(finish_reason, str) else None

    def _invalid_envelope(self, request_id: str, attempts: int) -> Never:
        raise ProviderError(
            ProviderErrorCode.INVALID_UPSTREAM_RESPONSE,
            message="The provider response is missing required structured content.",
            provider_name=self.provider_name,
            request_id=request_id,
            attempts=attempts,
        )


def _non_negative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

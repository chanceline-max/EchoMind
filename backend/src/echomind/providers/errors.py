"""Safe, provider-independent error contract."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ProviderErrorCode(StrEnum):
    PROVIDER_NOT_FOUND = "provider_not_found"
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    LOCAL_PROVIDER_NOT_CONFIGURED = "local_provider_not_configured"
    REMOTE_PROVIDER_DISABLED = "remote_provider_disabled"
    REMOTE_CONSENT_REQUIRED = "remote_consent_required"
    INVALID_PROVIDER_CONFIGURATION = "invalid_provider_configuration"
    INVALID_ENDPOINT = "invalid_endpoint"
    INPUT_BUDGET_EXCEEDED = "input_budget_exceeded"
    OUTPUT_BUDGET_EXCEEDED = "output_budget_exceeded"
    SCHEMA_TOO_LARGE = "schema_too_large"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    UPSTREAM_AUTH_ERROR = "upstream_auth_error"
    UPSTREAM_RATE_LIMITED = "upstream_rate_limited"
    UPSTREAM_CLIENT_ERROR = "upstream_client_error"
    UPSTREAM_SERVER_ERROR = "upstream_server_error"
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_UPSTREAM_RESPONSE = "invalid_upstream_response"
    INVALID_JSON_RESPONSE = "invalid_json_response"
    STRUCTURED_OUTPUT_VALIDATION_FAILED = "structured_output_validation_failed"
    RETRY_EXHAUSTED = "retry_exhausted"
    MOCK_SCENARIO_ERROR = "mock_scenario_error"


class ProviderError(Exception):
    """Controlled exception whose fields are safe to expose to application code."""

    def __init__(
        self,
        error_code: ProviderErrorCode | str,
        *,
        message: str,
        provider_name: str,
        request_id: str | None = None,
        recoverable: bool = False,
        attempts: int = 0,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = ProviderErrorCode(error_code)
        self.message = message
        self.provider_name = provider_name
        self.request_id = request_id
        self.recoverable = recoverable
        self.attempts = attempts
        self.status_code = status_code
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "provider_name": self.provider_name,
            "request_id": self.request_id,
            "recoverable": self.recoverable,
            "attempts": self.attempts,
            "status_code": self.status_code,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return (
            "ProviderError("
            f"error_code={self.error_code.value!r}, provider_name={self.provider_name!r}, "
            f"request_id={self.request_id!r}, recoverable={self.recoverable!r}, "
            f"attempts={self.attempts!r})"
        )

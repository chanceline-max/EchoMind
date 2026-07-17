"""OpenAI-compatible adapter tests using only httpx.MockTransport."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from echomind.providers import ProviderError, ProviderErrorCode
from tests.providers.factories import (
    SyntheticExtractionResult,
    limits,
    make_remote_provider,
    make_request,
    success_envelope,
)


def test_remote_success_sends_minimal_compatible_request() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=success_envelope(),
            headers={"x-request-id": "remote-safe-id", "openai-version": "synthetic-v1"},
        )

    provider = make_remote_provider(httpx.MockTransport(handler))
    request = make_request(
        provider_name="openai_compatible",
        model_name="synthetic-remote-model",
        remote_consent=True,
    )
    result = provider.generate_structured(request, SyntheticExtractionResult)

    assert captured["url"] == "https://models.example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer synthetic-secret-key"
    body = captured["body"]
    assert body["model"] == "synthetic-remote-model"
    assert body["messages"] == [
        {"role": "system", "content": "Return a synthetic JSON object."},
        {"role": "user", "content": "Synthetic input only."},
    ]
    assert body["stream"] is False
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert result.output.summary == "Synthetic summary"
    assert result.provider_metadata_json == {
        "remote_request_id": "remote-safe-id",
        "api_version": "synthetic-v1",
    }


@pytest.mark.parametrize(
    ("remote_enabled", "consent", "code"),
    [
        (False, False, ProviderErrorCode.REMOTE_PROVIDER_DISABLED),
        (False, True, ProviderErrorCode.REMOTE_PROVIDER_DISABLED),
        (True, False, ProviderErrorCode.REMOTE_CONSENT_REQUIRED),
    ],
)
def test_double_authorization_rejects_before_transport(
    remote_enabled: bool,
    consent: bool,
    code: ProviderErrorCode,
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=success_envelope())

    provider = make_remote_provider(httpx.MockTransport(handler), remote_enabled=remote_enabled)
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=consent,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is code
    assert calls == 0


def test_double_authorization_allows_transport_only_when_both_true() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=success_envelope())

    provider = make_remote_provider(httpx.MockTransport(handler), remote_enabled=True)
    provider.generate_structured(
        make_request(
            provider_name="openai_compatible",
            model_name="synthetic-remote-model",
            remote_consent=True,
        ),
        SyntheticExtractionResult,
    )
    assert calls == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"provider_name": "mock"},
        {"model_name": "caller-overrides-server-model"},
    ],
)
def test_request_cannot_override_server_provider_or_model(updates: dict[str, str]) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=success_envelope())

    provider = make_remote_provider(httpx.MockTransport(handler))
    request_values = {
        "provider_name": "openai_compatible",
        "model_name": "synthetic-remote-model",
        "remote_consent": True,
    }
    request_values.update(updates)
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(**request_values),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION
    assert calls == 0


@pytest.mark.parametrize(
    ("envelope", "code"),
    [
        ({}, ProviderErrorCode.INVALID_UPSTREAM_RESPONSE),
        ({"choices": []}, ProviderErrorCode.INVALID_UPSTREAM_RESPONSE),
        ({"choices": [{}]}, ProviderErrorCode.INVALID_UPSTREAM_RESPONSE),
        ({"choices": [{"message": {}}]}, ProviderErrorCode.INVALID_UPSTREAM_RESPONSE),
        ({"choices": [{"message": {"content": ""}}]}, ProviderErrorCode.INVALID_UPSTREAM_RESPONSE),
        (
            {"choices": [{"message": {"content": "not-json"}}]},
            ProviderErrorCode.INVALID_JSON_RESPONSE,
        ),
        (
            {"choices": [{"message": {"content": "{}"}}]},
            ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED,
        ),
    ],
)
def test_invalid_envelopes_and_content_are_controlled(
    envelope: dict[str, Any],
    code: ProviderErrorCode,
) -> None:
    provider = make_remote_provider(
        httpx.MockTransport(lambda _: httpx.Response(200, json=envelope))
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is code


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, ProviderErrorCode.UPSTREAM_CLIENT_ERROR),
        (401, ProviderErrorCode.UPSTREAM_AUTH_ERROR),
        (403, ProviderErrorCode.UPSTREAM_AUTH_ERROR),
        (404, ProviderErrorCode.UPSTREAM_CLIENT_ERROR),
        (302, ProviderErrorCode.INVALID_UPSTREAM_RESPONSE),
    ],
)
def test_permanent_http_errors_do_not_retry(status: int, code: ProviderErrorCode) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text="RESPONSE_MARKER_MUST_NOT_LEAK")

    provider = make_remote_provider(httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is code
    assert caught.value.attempts == 1
    assert calls == 1
    assert "RESPONSE_MARKER" not in repr(caught.value.as_dict())


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_retryable_http_status_recovers(status: int) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status)
        return httpx.Response(200, json=success_envelope())

    provider = make_remote_provider(httpx.MockTransport(handler), sleeper=sleeps.append)
    result = provider.generate_structured(
        make_request(
            provider_name="openai_compatible",
            model_name="synthetic-remote-model",
            remote_consent=True,
        ),
        SyntheticExtractionResult,
    )
    assert result.attempts == 2
    assert calls == 2
    assert sleeps == [0.1]


def test_retry_exhaustion_attempts_and_backoff_match_calls() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    provider = make_remote_provider(
        httpx.MockTransport(handler), max_retries=2, sleeper=sleeps.append
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is ProviderErrorCode.RETRY_EXHAUSTED
    assert caught.value.attempts == calls == 3
    assert sleeps == [0.1, 0.2]


@pytest.mark.parametrize(
    ("exception_factory", "last_code"),
    [
        (
            lambda request: httpx.ReadTimeout("synthetic timeout", request=request),
            ProviderErrorCode.TIMEOUT,
        ),
        (
            lambda request: httpx.ConnectError("synthetic connection", request=request),
            ProviderErrorCode.CONNECTION_ERROR,
        ),
    ],
)
def test_transport_errors_retry_without_real_sleep(
    exception_factory: Callable[[httpx.Request], Exception],
    last_code: ProviderErrorCode,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise exception_factory(request)

    provider = make_remote_provider(httpx.MockTransport(handler), max_retries=1)
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is ProviderErrorCode.RETRY_EXHAUSTED
    assert caught.value.details == {"last_error_code": last_code.value}
    assert caught.value.attempts == calls == 2


def test_unexpected_transport_exception_is_controlled() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise ValueError("LOCAL_PATH_MARKER C:\\Users\\private")

    provider = make_remote_provider(httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is ProviderErrorCode.INVALID_UPSTREAM_RESPONSE
    assert "LOCAL_PATH_MARKER" not in repr(caught.value.as_dict())


def test_keyboard_interrupt_is_not_swallowed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise KeyboardInterrupt

    provider = make_remote_provider(httpx.MockTransport(handler))
    with pytest.raises(KeyboardInterrupt):
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )


def test_response_size_is_checked_before_json_parsing() -> None:
    marker = b"RESPONSE_TOO_LARGE_MARKER"
    provider = make_remote_provider(
        httpx.MockTransport(lambda _: httpx.Response(200, content=marker * 10)),
        max_response_bytes=64,
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is ProviderErrorCode.RESPONSE_TOO_LARGE
    assert "RESPONSE_TOO_LARGE_MARKER" not in repr(caught.value.as_dict())


def test_unknown_content_type_is_reported_safely() -> None:
    provider = make_remote_provider(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=b"invalid-envelope",
                headers={"content-type": "application/x-synthetic"},
            )
        )
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.details == {"received_content_type": "application/x-synthetic"}


@pytest.mark.parametrize("finish_reason", ["stop", None])
@pytest.mark.parametrize("with_usage", [True, False])
def test_optional_usage_and_finish_reason(
    finish_reason: str | None,
    with_usage: bool,
) -> None:
    usage = {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14}
    provider = make_remote_provider(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json=success_envelope(
                    finish_reason=finish_reason,
                    usage=usage if with_usage else None,
                ),
            )
        )
    )
    result = provider.generate_structured(
        make_request(
            provider_name="openai_compatible",
            model_name="synthetic-remote-model",
            remote_consent=True,
        ),
        SyntheticExtractionResult,
    )
    assert result.finish_reason == finish_reason
    assert result.usage.input_tokens == (10 if with_usage else None)
    assert result.usage.output_tokens == (4 if with_usage else None)
    assert result.usage.total_tokens == (14 if with_usage else None)


@pytest.mark.parametrize(
    ("limit_updates", "request_updates", "code"),
    [
        ({"max_input_characters": 1}, {}, ProviderErrorCode.INPUT_BUDGET_EXCEEDED),
        (
            {"max_messages": 1},
            {
                "user_content": [
                    {"role": "user", "content": "one"},
                    {"role": "user", "content": "two"},
                ]
            },
            ProviderErrorCode.INPUT_BUDGET_EXCEEDED,
        ),
        (
            {"max_output_tokens": 10},
            {"max_output_tokens": 11},
            ProviderErrorCode.OUTPUT_BUDGET_EXCEEDED,
        ),
        ({"max_schema_characters": 10}, {}, ProviderErrorCode.SCHEMA_TOO_LARGE),
    ],
)
def test_budget_failure_never_reaches_transport(
    limit_updates: dict[str, int],
    request_updates: dict[str, Any],
    code: ProviderErrorCode,
) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=success_envelope())

    provider = make_remote_provider(httpx.MockTransport(handler), limits=limits(**limit_updates))
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-remote-model",
                remote_consent=True,
                **request_updates,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is code
    assert calls == 0

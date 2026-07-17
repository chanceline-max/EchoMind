"""Offline Mock, Local, Protocol, Factory, and retry behavior."""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr

from echomind.providers import (
    LLMProvider,
    LocalModelProvider,
    MockLLMProvider,
    OpenAICompatibleProvider,
    ProviderError,
    ProviderErrorCode,
    create_provider,
)
from tests.providers.factories import (
    REQUEST_ID,
    SyntheticExtractionResult,
    limits,
    make_request,
    make_settings,
)


def test_default_and_explicit_factory_create_mock() -> None:
    assert isinstance(create_provider(make_settings()), MockLLMProvider)
    assert isinstance(create_provider(make_settings(), provider_name="mock"), MockLLMProvider)


def test_provider_implementations_satisfy_runtime_protocol() -> None:
    mock = create_provider(make_settings())
    local = create_provider(make_settings(), provider_name="local")
    assert isinstance(mock, LLMProvider)
    assert isinstance(local, LLMProvider)


def test_unknown_provider_is_controlled() -> None:
    with pytest.raises(ProviderError) as caught:
        create_provider(make_settings(), provider_name="unknown")
    assert caught.value.error_code is ProviderErrorCode.PROVIDER_NOT_FOUND


def test_openai_factory_requires_complete_configuration() -> None:
    with pytest.raises(ProviderError) as caught:
        create_provider(make_settings(llm_provider="openai_compatible"))
    assert caught.value.error_code is ProviderErrorCode.PROVIDER_NOT_CONFIGURED


def test_openai_factory_builds_without_network_probe() -> None:
    provider = create_provider(
        make_settings(
            llm_provider="openai_compatible",
            llm_openai_compatible_endpoint="https://models.example.test/v1/chat/completions",
            llm_openai_compatible_api_key=SecretStr("synthetic-key"),
            llm_openai_compatible_model="synthetic-model",
        )
    )
    assert isinstance(provider, OpenAICompatibleProvider)


def test_local_provider_is_explicitly_unavailable() -> None:
    provider = LocalModelProvider()
    assert provider.available is False
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(make_request(provider_name="local"), SyntheticExtractionResult)
    assert caught.value.error_code is ProviderErrorCode.LOCAL_PROVIDER_NOT_CONFIGURED


def test_mock_success_returns_fully_validated_result() -> None:
    provider = MockLLMProvider(
        response_payload={"summary": "Stable", "labels": ["fixture"]},
        limits=limits(),
    )
    request = make_request()
    result = provider.generate_structured(request, SyntheticExtractionResult)
    assert result.request_id == REQUEST_ID
    assert result.output == SyntheticExtractionResult(summary="Stable", labels=["fixture"])
    assert result.provider_name == "mock"
    assert result.attempts == 1
    assert result.duration_ms == 0
    assert result.usage.input_tokens is None
    assert result.usage.estimated_output_limit == request.max_output_tokens


def test_mock_same_input_has_stable_serialization() -> None:
    provider = MockLLMProvider(limits=limits())
    request = make_request()
    first = provider.generate_structured(request, SyntheticExtractionResult)
    second = provider.generate_structured(request, SyntheticExtractionResult)
    assert first.model_dump_json() == second.model_dump_json()


@pytest.mark.parametrize(
    ("scenario", "code", "attempts"),
    [
        ("invalid_json", ProviderErrorCode.INVALID_JSON_RESPONSE, 1),
        ("schema_mismatch", ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED, 1),
        ("permanent_error", ProviderErrorCode.MOCK_SCENARIO_ERROR, 1),
        ("empty_response", ProviderErrorCode.INVALID_UPSTREAM_RESPONSE, 1),
        ("timeout", ProviderErrorCode.RETRY_EXHAUSTED, 3),
        ("retry_exhausted", ProviderErrorCode.RETRY_EXHAUSTED, 3),
    ],
)
def test_mock_failure_scenarios_are_explicit(
    scenario: str,
    code: ProviderErrorCode,
    attempts: int,
) -> None:
    provider = MockLLMProvider(scenario=scenario, limits=limits(), sleeper=lambda _: None)  # type: ignore[arg-type]
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(make_request(), SyntheticExtractionResult)
    assert caught.value.error_code is code
    assert caught.value.attempts == attempts


def test_mock_transient_error_retries_once_then_succeeds() -> None:
    sleeps: list[float] = []
    provider = MockLLMProvider(
        scenario="transient_error_then_success",
        limits=limits(),
        sleeper=sleeps.append,
    )
    result = provider.generate_structured(make_request(), SyntheticExtractionResult)
    assert result.attempts == 2
    assert sleeps == [0.1]


def test_mock_retry_backoff_is_stable_and_does_not_sleep_in_test() -> None:
    sleeps: list[float] = []
    provider = MockLLMProvider(
        scenario="timeout",
        max_retries=2,
        limits=limits(),
        sleeper=sleeps.append,
    )
    with pytest.raises(ProviderError):
        provider.generate_structured(make_request(), SyntheticExtractionResult)
    assert sleeps == [0.1, 0.2]


def test_mock_timeout_without_retries_preserves_timeout_code() -> None:
    provider = MockLLMProvider(
        scenario="timeout",
        max_retries=0,
        limits=limits(),
        sleeper=lambda _: None,
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(make_request(), SyntheticExtractionResult)
    assert caught.value.error_code is ProviderErrorCode.TIMEOUT
    assert caught.value.attempts == 1


def test_mock_rejects_provider_name_mismatch() -> None:
    with pytest.raises(ProviderError) as caught:
        MockLLMProvider(limits=limits()).generate_structured(
            make_request(provider_name="openai_compatible"),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION


def test_mock_does_not_require_remote_consent_or_read_environment_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_OPENAI_COMPATIBLE_API_KEY", "REAL_ENV_MARKER_MUST_NOT_BE_READ")
    result = MockLLMProvider(limits=limits()).generate_structured(
        make_request(remote_consent=False), SyntheticExtractionResult
    )
    assert result.output.summary == "Synthetic summary"
    assert "REAL_ENV_MARKER" not in result.model_dump_json()
    assert os.environ["LLM_OPENAI_COMPATIBLE_API_KEY"].startswith("REAL_ENV")


def test_factory_module_has_no_database_dependencies() -> None:
    import echomind.providers.factory as factory_module

    source_names = set(factory_module.__dict__)
    assert "Session" not in source_names
    assert "Message" not in source_names

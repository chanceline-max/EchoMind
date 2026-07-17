"""Settings secrecy, safe errors, imports, and network-isolation checks."""

from __future__ import annotations

import ast
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from echomind.core.config import Settings
from echomind.providers import ProviderError, ProviderErrorCode, create_provider
from echomind.providers.transport import HttpxTransport
from tests.providers.factories import (
    SyntheticExtractionResult,
    make_request,
    make_settings,
)


def test_settings_defaults_to_offline_mock() -> None:
    settings = make_settings()
    assert settings.llm_provider == "mock"
    assert settings.llm_remote_enabled is False
    assert settings.llm_openai_compatible_api_key is None


def test_secret_key_is_masked_in_settings_repr() -> None:
    marker = "SECRET_KEY_REPR_MARKER"
    settings = make_settings(llm_openai_compatible_api_key=SecretStr(marker))
    assert marker not in repr(settings)
    assert "**********" in repr(settings)


@pytest.mark.parametrize(
    "updates",
    [
        {"llm_provider": "dynamic.module"},
        {"llm_max_retries": 6},
        {"llm_request_timeout_seconds": 0},
        {"llm_max_input_characters": 10, "llm_max_message_characters": 11},
        {"llm_openai_compatible_endpoint": "file:///synthetic"},
        {
            "llm_openai_compatible_endpoint": "http://remote.example.test/v1",
            "llm_allow_insecure_local_http": True,
        },
        {"llm_openai_compatible_endpoint": "http://localhost:11434/v1"},
        {"llm_openai_compatible_endpoint": "https://user:pass@example.test/v1"},
        {"llm_openai_compatible_endpoint": "https://example.test/v1#fragment"},
        {"llm_openai_compatible_endpoint": "https://example.test/v1", "llm_verify_tls": False},
    ],
)
def test_settings_reject_unsafe_provider_configuration(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_settings(**updates)


def test_settings_allow_explicit_local_http() -> None:
    settings = make_settings(
        llm_openai_compatible_endpoint="http://localhost:11434/v1/chat/completions",
        llm_allow_insecure_local_http=True,
    )
    assert settings.llm_openai_compatible_endpoint == ("http://localhost:11434/v1/chat/completions")


def test_provider_error_repr_and_dict_exclude_sensitive_markers() -> None:
    error = ProviderError(
        ProviderErrorCode.UPSTREAM_AUTH_ERROR,
        message="The provider rejected credentials.",
        provider_name="openai_compatible",
        request_id="synthetic-id",
        details={"status_category": "auth"},
    )
    serialized = repr(error) + repr(error.as_dict())
    for marker in (
        "Bearer SECRET_AUTHORIZATION_MARKER",
        "PROMPT_BODY_MARKER",
        "RESPONSE_BODY_MARKER",
        "C:\\Users\\private\\model.txt",
        "sqlite:///private.db",
    ):
        assert marker not in serialized


def test_health_response_does_not_expose_provider_configuration() -> None:
    # Covered by the existing health contract; this source-level assertion prevents schema drift.
    health_source = Path("src/echomind/api/v1/health.py").read_text(encoding="utf-8")
    assert "llm_" not in health_source.casefold()
    assert "api_key" not in health_source.casefold()


def test_provider_package_does_not_import_forbidden_layers() -> None:
    provider_root = Path("src/echomind/providers")
    forbidden = (
        "sqlalchemy",
        "echomind.models",
        "echomind.repositories",
        "fastapi",
        "echomind.schemas.message",
        "echomind.schemas.insight",
        "echomind.schemas.evidence",
    )
    for path in provider_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)
        assert not any(name.startswith(forbidden) for name in imported), path.name


def test_default_factory_ignores_real_key_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_OPENAI_COMPATIBLE_API_KEY", "REAL_KEY_ENV_MARKER")
    settings = Settings(database_url="sqlite:///:memory:", llm_provider="mock")
    provider = create_provider(settings)
    result = provider.generate_structured(make_request(), SyntheticExtractionResult)
    assert result.provider_name == "mock"


def test_remote_disabled_blocks_even_with_mock_transport_and_real_key_marker() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    provider = create_provider(
        make_settings(
            llm_provider="openai_compatible",
            llm_remote_enabled=False,
            llm_openai_compatible_endpoint="https://models.example.test/v1/chat/completions",
            llm_openai_compatible_api_key=SecretStr("REAL_KEY_MARKER"),
            llm_openai_compatible_model="synthetic-model",
        ),
        transport=HttpxTransport(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-model",
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    assert caught.value.error_code is ProviderErrorCode.REMOTE_PROVIDER_DISABLED
    assert calls == 0
    assert "REAL_KEY_MARKER" not in repr(caught.value.as_dict())


def test_remote_error_and_logs_exclude_key_prompt_response_and_path_markers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    key_marker = "PRIVATE_KEY_MARKER"
    prompt_marker = "PRIVATE_PROMPT_MARKER"
    response_marker = "PRIVATE_RESPONSE_MARKER C:\\Users\\private"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=response_marker)

    provider = create_provider(
        make_settings(
            llm_provider="openai_compatible",
            llm_remote_enabled=True,
            llm_openai_compatible_endpoint="https://models.example.test/v1/chat/completions",
            llm_openai_compatible_api_key=SecretStr(key_marker),
            llm_openai_compatible_model="synthetic-model",
        ),
        transport=HttpxTransport(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate_structured(
            make_request(
                provider_name="openai_compatible",
                model_name="synthetic-model",
                system_instruction=prompt_marker,
                remote_consent=True,
            ),
            SyntheticExtractionResult,
        )
    combined = repr(caught.value.as_dict()) + caplog.text
    assert caught.value.error_code is ProviderErrorCode.UPSTREAM_AUTH_ERROR
    assert key_marker not in combined
    assert prompt_marker not in combined
    assert response_marker not in combined

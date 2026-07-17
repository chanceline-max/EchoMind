"""Closed provider factory; no dynamic imports and no network probes."""

from typing import Any

from pydantic import SecretStr

from echomind.core.config import Settings
from echomind.providers.base import LLMProvider
from echomind.providers.errors import ProviderError, ProviderErrorCode
from echomind.providers.local import LocalModelProvider
from echomind.providers.mock import MockLLMProvider, MockScenario
from echomind.providers.openai_compatible import OpenAICompatibleProvider
from echomind.providers.retry import Sleeper, default_sleeper
from echomind.providers.transport import HTTPTransport
from echomind.providers.validation import BudgetLimits


def budget_limits_from_settings(settings: Settings) -> BudgetLimits:
    return BudgetLimits(
        max_input_characters=settings.llm_max_input_characters,
        max_messages=settings.llm_max_messages,
        max_message_characters=settings.llm_max_message_characters,
        max_schema_characters=settings.llm_max_schema_characters,
        max_output_tokens=settings.llm_max_output_tokens,
    )


def create_provider(
    settings: Settings,
    *,
    provider_name: str | None = None,
    transport: HTTPTransport | None = None,
    mock_scenario: MockScenario = "success",
    mock_response_payload: dict[str, Any] | None = None,
    sleeper: Sleeper = default_sleeper,
) -> LLMProvider:
    """Build a provider without testing connectivity or reading any database."""
    selected = provider_name or settings.llm_provider
    limits = budget_limits_from_settings(settings)
    if selected == "mock":
        return MockLLMProvider(
            response_payload=mock_response_payload,
            scenario=mock_scenario,
            max_retries=settings.llm_max_retries,
            limits=limits,
            sleeper=sleeper,
        )
    if selected == "local":
        return LocalModelProvider()
    if selected == "openai_compatible":
        endpoint = settings.llm_openai_compatible_endpoint
        api_key = settings.llm_openai_compatible_api_key
        model_name = settings.llm_openai_compatible_model
        if endpoint is None or api_key is None or model_name is None:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_NOT_CONFIGURED,
                message="The OpenAI-compatible provider configuration is incomplete.",
                provider_name=selected,
            )
        return OpenAICompatibleProvider(
            endpoint=endpoint,
            api_key=SecretStr(api_key.get_secret_value()),
            model_name=model_name,
            remote_enabled=settings.llm_remote_enabled,
            allow_insecure_local_http=settings.llm_allow_insecure_local_http,
            verify_tls=settings.llm_verify_tls,
            request_timeout_seconds=settings.llm_request_timeout_seconds,
            connect_timeout_seconds=settings.llm_connect_timeout_seconds,
            read_timeout_seconds=settings.llm_read_timeout_seconds,
            max_retries=settings.llm_max_retries,
            max_response_bytes=settings.llm_max_response_bytes,
            limits=limits,
            transport=transport,
            sleeper=sleeper,
        )
    raise ProviderError(
        ProviderErrorCode.PROVIDER_NOT_FOUND,
        message="The requested provider is not registered.",
        provider_name=selected,
    )

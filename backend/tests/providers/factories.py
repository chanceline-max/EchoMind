"""Synthetic-only provider fixtures; never use real chat content or network."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from echomind.core.config import Settings
from echomind.providers import (
    BudgetLimits,
    HttpxTransport,
    LLMContent,
    LLMRequest,
    OpenAICompatibleProvider,
)

REQUEST_ID = UUID("00000000-0000-4000-8000-000000000006")


class NestedSynthetic(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    score: int = Field(ge=0)


class SyntheticExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str
    labels: list[str]
    nested: NestedSynthetic | None = None


def make_request(**updates: Any) -> LLMRequest:
    values: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "system_instruction": "Return a synthetic JSON object.",
        "user_content": [LLMContent(role="user", content="Synthetic input only.")],
        "response_schema_name": "SyntheticExtractionResult",
        "provider_name": "mock",
        "model_name": "synthetic-model",
        "temperature": 0.0,
        "max_output_tokens": 128,
        "timeout_seconds": 10.0,
        "metadata_json": {"pipeline_stage": "provider_contract", "source_count": 1},
        "remote_consent": False,
        "request_version": "1.0",
    }
    values.update(updates)
    return LLMRequest(**values)


def make_settings(**updates: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": "sqlite:///:memory:",
        "llm_provider": "mock",
        "llm_remote_enabled": False,
    }
    values.update(updates)
    return Settings(**values)


def limits(**updates: int) -> BudgetLimits:
    values = {
        "max_input_characters": 10_000,
        "max_messages": 10,
        "max_message_characters": 2_000,
        "max_schema_characters": 50_000,
        "max_output_tokens": 2_000,
    }
    values.update(updates)
    return BudgetLimits(**values)


def make_remote_provider(
    handler: httpx.MockTransport,
    **updates: Any,
) -> OpenAICompatibleProvider:
    values: dict[str, Any] = {
        "endpoint": "https://models.example.test/v1/chat/completions",
        "api_key": SecretStr("synthetic-secret-key"),
        "model_name": "synthetic-remote-model",
        "remote_enabled": True,
        "allow_insecure_local_http": False,
        "verify_tls": True,
        "request_timeout_seconds": 30.0,
        "connect_timeout_seconds": 5.0,
        "read_timeout_seconds": 30.0,
        "max_retries": 2,
        "max_response_bytes": 1_048_576,
        "limits": limits(),
        "transport": HttpxTransport(transport=handler),
        "sleeper": lambda _: None,
    }
    values.update(updates)
    return OpenAICompatibleProvider(**values)


def success_envelope(
    *,
    content: str = '{"summary":"Synthetic summary","labels":["safe"]}',
    finish_reason: str | None = "stop",
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    choice: dict[str, Any] = {"message": {"content": content}}
    if finish_reason is not None:
        choice["finish_reason"] = finish_reason
    envelope: dict[str, Any] = {"choices": [choice]}
    if usage is not None:
        envelope["usage"] = usage
    return envelope

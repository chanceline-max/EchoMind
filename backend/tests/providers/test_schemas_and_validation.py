"""Strict request, endpoint, budget, and output validation tests."""

from __future__ import annotations

from typing import Any, cast

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from echomind.providers import LLMContent, LLMRequest, ProviderError, ProviderErrorCode
from echomind.providers.validation import (
    parse_structured_output,
    validate_endpoint,
    validate_request_budget,
)
from tests.providers.factories import (
    REQUEST_ID,
    SyntheticExtractionResult,
    limits,
    make_request,
)


@pytest.mark.parametrize(
    "updates",
    [
        {"system_instruction": ""},
        {"system_instruction": "   "},
        {"user_content": []},
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"max_output_tokens": 0},
        {"timeout_seconds": 0.0},
        {"response_schema_name": "unsafe name"},
        {"provider_name": "unsafe/name"},
    ],
)
def test_request_rejects_invalid_fields(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        make_request(**updates)


def test_request_is_strict_and_forbids_extra_fields() -> None:
    data = make_request().model_dump()
    data["max_output_tokens"] = "128"
    data["unexpected"] = True
    with pytest.raises(ValidationError):
        LLMRequest.model_validate(data)


@pytest.mark.parametrize(
    "metadata",
    [
        {"api_key": "marker"},
        {"Authorization": "Bearer marker"},
        {"database_url": "sqlite:///marker"},
        {"raw_content": "marker"},
        {"access_token": "marker"},
        {"pipeline_stage": "C:\\Users\\private\\marker.txt"},
        {"pipeline_stage": "https://private.example.test/marker"},
        {"pipeline_stage": "Bearer secret-marker"},
    ],
)
def test_request_rejects_sensitive_metadata_keys(metadata: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        make_request(metadata_json=metadata)


def test_content_allows_only_user_role() -> None:
    with pytest.raises(ValidationError):
        LLMContent(role="assistant", content="synthetic")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("endpoint", "allow_insecure"),
    [
        ("https://api.example.test/v1/chat/completions", False),
        ("https://localhost/v1/chat/completions", False),
        ("http://localhost:11434/v1/chat/completions", True),
        ("http://127.0.0.1:11434/v1/chat/completions", True),
        ("http://[::1]:11434/v1/chat/completions", True),
    ],
)
def test_endpoint_accepts_allowed_urls(endpoint: str, allow_insecure: bool) -> None:
    assert validate_endpoint(endpoint, allow_insecure_local_http=allow_insecure) == endpoint


@pytest.mark.parametrize(
    ("endpoint", "allow_insecure"),
    [
        ("http://localhost:11434/v1", False),
        ("http://example.test/v1", True),
        ("file:///tmp/model", True),
        ("ftp://example.test/model", True),
        ("relative/path", True),
        ("https://user:password@example.test/v1", False),
        ("https://example.test/v1#secret", False),
        ("x" * 2_049, False),
    ],
)
def test_endpoint_rejects_unsafe_urls(endpoint: str, allow_insecure: bool) -> None:
    with pytest.raises(ValueError):
        validate_endpoint(endpoint, allow_insecure_local_http=allow_insecure)


@pytest.mark.parametrize(
    ("llm_request", "budget", "code", "limit_name"),
    [
        (
            make_request(user_content=[LLMContent(content="a"), LLMContent(content="b")]),
            limits(max_messages=1),
            ProviderErrorCode.INPUT_BUDGET_EXCEEDED,
            "message_count",
        ),
        (
            make_request(user_content=[LLMContent(content="long")]),
            limits(max_message_characters=3),
            ProviderErrorCode.INPUT_BUDGET_EXCEEDED,
            "message_characters",
        ),
        (
            make_request(system_instruction="1234", user_content=[LLMContent(content="56")]),
            limits(max_input_characters=5),
            ProviderErrorCode.INPUT_BUDGET_EXCEEDED,
            "input_characters",
        ),
        (
            make_request(max_output_tokens=129),
            limits(max_output_tokens=128),
            ProviderErrorCode.OUTPUT_BUDGET_EXCEEDED,
            "max_output_tokens",
        ),
    ],
)
def test_budget_errors_are_safe(
    llm_request: LLMRequest,
    budget: Any,
    code: ProviderErrorCode,
    limit_name: str,
) -> None:
    with pytest.raises(ProviderError) as caught:
        validate_request_budget(llm_request, SyntheticExtractionResult, budget)
    assert caught.value.error_code is code
    assert caught.value.details["limit_name"] == limit_name
    assert set(caught.value.details) == {"limit_name", "allowed", "actual"}
    assert "Synthetic input only" not in repr(caught.value.as_dict())


def test_schema_budget_is_checked() -> None:
    fields = {f"field_{index}": (str, ...) for index in range(20)}
    HugeSchema = create_model(
        "HugeSchema",
        __config__=ConfigDict(extra="forbid", strict=True),
        **cast(dict[str, Any], fields),
    )
    with pytest.raises(ProviderError) as caught:
        validate_request_budget(make_request(), HugeSchema, limits(max_schema_characters=50))
    assert caught.value.error_code is ProviderErrorCode.SCHEMA_TOO_LARGE


def test_unserializable_schema_is_a_controlled_error() -> None:
    invalid_schema = cast(type[BaseModel], object)
    with pytest.raises(ProviderError) as caught:
        validate_request_budget(make_request(), invalid_schema, limits())
    assert caught.value.error_code is ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION


def test_response_schema_must_forbid_extra_fields() -> None:
    class LooseResult(BaseModel):
        value: str

    with pytest.raises(ProviderError) as caught:
        validate_request_budget(make_request(), LooseResult, limits())
    assert caught.value.error_code is ProviderErrorCode.INVALID_PROVIDER_CONFIGURATION


def test_valid_budget_returns_character_count_not_token_claim() -> None:
    request = make_request()
    characters, schema = validate_request_budget(request, SyntheticExtractionResult, limits())
    assert characters == len(request.system_instruction) + len(request.user_content[0].content)
    assert "summary" in schema


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("not-json", ProviderErrorCode.INVALID_JSON_RESPONSE),
        ("```json\n{}\n```", ProviderErrorCode.INVALID_JSON_RESPONSE),
        ("{}", ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED),
        (
            '{"summary":"ok","labels":[],"extra":true}',
            ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED,
        ),
        (
            '{"summary":"ok","labels":"wrong"}',
            ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED,
        ),
        (
            '{"summary":"ok","labels":[],"nested":{"score":"1"}}',
            ProviderErrorCode.STRUCTURED_OUTPUT_VALIDATION_FAILED,
        ),
    ],
)
def test_structured_output_rejects_invalid_data(
    content: str,
    code: ProviderErrorCode,
) -> None:
    with pytest.raises(ProviderError) as caught:
        parse_structured_output(
            content,
            response_schema=SyntheticExtractionResult,
            provider_name="mock",
            request_id=str(REQUEST_ID),
            attempts=1,
        )
    assert caught.value.error_code is code
    assert content not in repr(caught.value.as_dict())


def test_structured_output_returns_requested_model() -> None:
    output = parse_structured_output(
        '{"summary":"ok","labels":["synthetic"],"nested":{"score":1}}',
        response_schema=SyntheticExtractionResult,
        provider_name="mock",
        request_id=str(REQUEST_ID),
        attempts=1,
    )
    assert isinstance(output, SyntheticExtractionResult)
    assert output.nested is not None and output.nested.score == 1


def test_structured_validation_details_never_include_rejected_values() -> None:
    marker = "REJECTED_RESPONSE_MARKER"
    with pytest.raises(ProviderError) as caught:
        parse_structured_output(
            f'{{"summary":"{marker}","labels":"wrong"}}',
            response_schema=SyntheticExtractionResult,
            provider_name="mock",
            request_id=str(REQUEST_ID),
            attempts=1,
        )
    assert marker not in repr(caught.value.as_dict())


def test_arbitrary_strict_response_model_is_supported() -> None:
    class OtherResult(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        count: int

    output = parse_structured_output(
        '{"count":2}',
        response_schema=OtherResult,
        provider_name="mock",
        request_id=str(REQUEST_ID),
        attempts=1,
    )
    assert output == OtherResult(count=2)

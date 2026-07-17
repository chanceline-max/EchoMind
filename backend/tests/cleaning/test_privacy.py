"""Cleaning traces and failures must not leak synthetic sensitive canaries."""

import inspect
from pathlib import Path

import pytest

import echomind.cleaning as cleaning_package
from echomind.cleaning.errors import CleaningError, CleaningErrorCode
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat

from .factories import message, parsed_chat

CANARY = "PRIVATE-CONTENT-CANARY"
EMAIL = "private.person@example.invalid"
URL = "https://private.invalid/opaque"


def test_operations_and_statistics_do_not_contain_original_values() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0] = message(content=f" {CANARY} {EMAIL} {URL} ")

    result = clean_chat(source, CleaningOptions(redact_sensitive_data=True))
    cleaned = result.conversations[0].cleaned_messages[0]
    traces = str([item.model_dump() for item in cleaned.cleaning_operations])
    statistics = result.statistics.model_dump_json()

    for secret in (CANARY, EMAIL, URL):
        assert secret not in traces
        assert secret not in statistics


def test_cleaning_error_keeps_only_safe_basename_and_structural_details() -> None:
    error = CleaningError(
        CleaningErrorCode.INVALID_CONFIGURATION,
        safe_filename=r"C:\Users\Synthetic\private-chat.json",
        cleaner_name="redaction",
        message="Cleaning configuration is invalid.",
        conversation_source_id="conversation-1",
        message_source_id="message-1",
        recoverable=False,
        details={"field": "custom_redaction_patterns"},
    )

    assert error.safe_filename == "private-chat.json"
    assert "C:\\Users" not in str(error)
    assert CANARY not in error.as_dict().values()


def test_schema_rejects_unsafe_operation_detail_keys() -> None:
    from echomind.cleaning.schemas import CleaningOperation

    with pytest.raises(ValueError):
        CleaningOperation(
            cleaner_name="synthetic",
            cleaner_version="1.0",
            operation_type="test",
            changed_fields=["normalized_content"],
            details={"raw_content": CANARY},
        )


def test_cleaning_package_has_no_database_network_or_upload_imports() -> None:
    package_dir = Path(inspect.getfile(cleaning_package)).parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in package_dir.glob("*.py")
    ).lower()

    forbidden = (
        "echomind.models",
        "echomind.db",
        "sqlalchemy",
        "uploadfile",
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "openai",
        "anthropic",
    )
    assert all(item not in source for item in forbidden)


def test_cleaning_source_does_not_assign_raw_content_or_filter_messages() -> None:
    package_dir = Path(inspect.getfile(cleaning_package)).parent
    source = "\n".join(path.read_text(encoding="utf-8") for path in package_dir.glob("*.py"))

    assert ".raw_content =" not in source
    assert "del cleaned_messages" not in source
    assert "remove(" not in source

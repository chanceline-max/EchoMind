"""End-to-end cleaning pipeline contract tests."""

import pytest

from echomind.cleaning.base import CleaningState
from echomind.cleaning.errors import CleaningError
from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import CLEANER_ORDER, CleaningPipeline, clean_chat
from echomind.cleaning.whitespace import WhitespaceCleaner

from .factories import message, parsed_chat

EXPECTED_ORDER = (
    "whitespace",
    "attachment_placeholders",
    "system_classification",
    "recalled_classification",
    "exact_duplicates",
    "url_replacement",
    "redaction",
    "exclusion",
    "analysis_units",
)


def disabled_options() -> CleaningOptions:
    return CleaningOptions(
        normalize_whitespace=False,
        normalize_line_endings=False,
        add_attachment_placeholders=False,
        classify_system_messages=False,
        classify_recalled_messages=False,
        detect_exact_duplicates=False,
        replace_urls=False,
        redact_sensitive_data=False,
        exclude_system_messages=False,
        exclude_recalled_messages=False,
        exclude_duplicates=False,
        build_analysis_units=False,
    )


def test_default_pipeline_order_is_fixed_and_documented() -> None:
    assert CLEANER_ORDER == EXPECTED_ORDER


def test_pipeline_preserves_source_and_parser_information() -> None:
    source = parsed_chat()

    result = clean_chat(source)

    assert result.source_filename == source.source_filename
    assert result.file_hash == source.file_hash
    assert result.parser_name == source.parser_name
    assert result.parser_version == source.parser_version
    assert result.parser_warnings == source.warnings
    assert result.cleaning_warnings == []


def test_pipeline_does_not_mutate_parser_input_or_drop_messages() -> None:
    source = parsed_chat()
    before = source.model_dump_json()

    result = clean_chat(source)

    assert source.model_dump_json() == before
    assert result.statistics.input_message_count == 1
    assert result.statistics.output_message_count == 1
    assert result.conversations[0].cleaned_messages[0].raw_content == "Synthetic message"


def test_no_cleaners_still_produces_valid_output() -> None:
    source = parsed_chat()

    result = clean_chat(source, disabled_options())
    cleaned = result.conversations[0].cleaned_messages[0]

    assert cleaned.normalized_content == cleaned.raw_content
    assert cleaned.cleaning_operations == []
    assert result.conversations[0].analysis_units == []
    assert all(count == 0 for count in result.statistics.per_cleaner_counts.values())


def test_cleaning_always_initializes_normalized_content_from_raw() -> None:
    source = parsed_chat()
    source.conversations[0].messages[0].normalized_content = "stale derived value"

    result = clean_chat(source, disabled_options())

    assert result.conversations[0].cleaned_messages[0].normalized_content == "Synthetic message"


def test_same_source_and_options_are_serialization_stable() -> None:
    source = parsed_chat()
    options = CleaningOptions()

    first = clean_chat(source, options)
    second = clean_chat(source, options)

    assert first.model_dump_json() == second.model_dump_json()


def test_pipeline_only_accepts_parsed_chat_file() -> None:
    cleaned = clean_chat(parsed_chat())

    with pytest.raises(TypeError, match="ParsedChatFile"):
        clean_chat(cleaned)  # type: ignore[arg-type]


def test_unexpected_cleaner_error_is_safe_and_returns_no_partial_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(
        cleaner: WhitespaceCleaner,
        state: CleaningState,
        options: CleaningOptions,
    ) -> int:
        state.conversations[0].cleaned_messages[0].normalized_content = "partial"
        raise RuntimeError("PRIVATE-CANARY should not escape")

    monkeypatch.setattr(WhitespaceCleaner, "apply", explode)

    with pytest.raises(CleaningError) as captured:
        CleaningPipeline().run(parsed_chat())

    assert captured.value.error_code == "internal_cleaner_error"
    assert captured.value.cleaner_name == "whitespace"
    assert "PRIVATE-CANARY" not in str(captured.value)
    assert captured.value.details == {"exception_type": "RuntimeError"}


def test_message_removal_by_internal_cleaner_invalidates_whole_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def drop(
        cleaner: WhitespaceCleaner,
        state: CleaningState,
        options: CleaningOptions,
    ) -> int:
        state.conversations[0].cleaned_messages.pop()
        return 1

    monkeypatch.setattr(WhitespaceCleaner, "apply", drop)

    with pytest.raises(CleaningError) as captured:
        CleaningPipeline().run(parsed_chat())

    assert captured.value.error_code == "invalid_cleaned_result"
    assert captured.value.recoverable is False


def test_raw_change_by_internal_cleaner_invalidates_whole_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mutate_raw(
        cleaner: WhitespaceCleaner,
        state: CleaningState,
        options: CleaningOptions,
    ) -> int:
        state.conversations[0].cleaned_messages[0].raw_content = "changed"
        return 1

    monkeypatch.setattr(WhitespaceCleaner, "apply", mutate_raw)

    with pytest.raises(CleaningError) as captured:
        CleaningPipeline().run(parsed_chat())

    assert captured.value.error_code == "invalid_cleaned_result"


def test_pipeline_keeps_conversation_and_participant_copies_independent() -> None:
    source = parsed_chat()
    result = clean_chat(source)

    result.conversations[0].participants[0].display_name = "Changed copy"
    result.conversations[0].metadata_json["fixture"] = False

    assert source.conversations[0].participants[0].display_name == "Synthetic person-a"
    assert source.conversations[0].metadata_json["fixture"] is True


def test_pipeline_handles_multiple_synthetic_messages_without_loss() -> None:
    source = parsed_chat()
    source.conversations[0].messages = [
        message(f"message-{index}", source_order=index, seconds=index) for index in range(500)
    ]
    source.statistics.message_count = 500
    source.statistics.accepted_record_count = 500

    result = clean_chat(source)

    assert len(result.conversations[0].cleaned_messages) == 500
    assert result.statistics.input_message_count == result.statistics.output_message_count == 500

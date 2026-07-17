"""Cleaning statistics consistency and recomputation tests."""

import pytest

from echomind.cleaning.options import CleaningOptions
from echomind.cleaning.pipeline import clean_chat, validate_cleaned_chat
from echomind.cleaning.schemas import CleanedChatFile
from echomind.parsers.schemas import MessageType

from .factories import conversation, message, parsed_chat


def rich_result() -> CleanedChatFile:
    source = parsed_chat(
        [
            conversation(
                [
                    message(
                        "system",
                        content="event",
                        message_type=MessageType.SYSTEM,
                        source_order=0,
                    ),
                    message("recalled", content="撤回了一条消息", source_order=1),
                    message("url", content=" https://example.invalid ", source_order=2),
                    message("duplicate", content=" https://example.invalid ", source_order=3),
                    message("email", content="person@example.invalid", source_order=4),
                    message("image", content="", message_type=MessageType.IMAGE, source_order=5),
                ]
            )
        ]
    )
    return clean_chat(source, CleaningOptions(redact_sensitive_data=True))


def test_statistics_match_final_result() -> None:
    result = rich_result()
    stats = result.statistics

    assert stats.conversation_count == 1
    assert stats.input_message_count == stats.output_message_count == 6
    assert stats.normalized_message_count == 4
    assert stats.system_message_count == 1
    assert stats.recalled_message_count == 1
    assert stats.duplicate_message_count == 1
    assert stats.excluded_message_count == 3
    assert stats.redacted_message_count == 1
    assert stats.redaction_count == 1
    assert stats.url_replacement_count == 2
    assert stats.attachment_placeholder_count == 1
    assert stats.analysis_unit_count == 2
    assert stats.warning_count == 0


def test_per_cleaner_counts_are_complete_and_safe() -> None:
    result = rich_result()

    assert result.statistics.per_cleaner_counts == {
        "whitespace": 2,
        "attachment_placeholders": 1,
        "system_classification": 1,
        "recalled_classification": 1,
        "exact_duplicates": 1,
        "url_replacement": 2,
        "redaction": 1,
        "exclusion": 3,
        "analysis_units": 2,
    }
    assert "example.invalid" not in result.statistics.model_dump_json()


def test_final_validation_recomputes_statistics_without_mutation() -> None:
    result = rich_result()
    before = result.model_dump_json()

    validated = validate_cleaned_chat(result)

    assert validated is result
    assert result.model_dump_json() == before


def test_tampered_statistics_are_rejected() -> None:
    result = rich_result()
    result.statistics.output_message_count = 999

    try:
        validate_cleaned_chat(result)
    except ValueError as error:
        assert str(error) == "cleaning statistics do not match final output"
    else:
        raise AssertionError("tampered statistics were accepted")


def test_tampered_per_cleaner_counts_are_rejected() -> None:
    result = rich_result()
    result.statistics.per_cleaner_counts["redaction"] = 999

    with pytest.raises(ValueError, match="cleaning statistics do not match final output"):
        validate_cleaned_chat(result)


def test_tampered_analysis_unit_content_is_rejected() -> None:
    result = rich_result()
    result.conversations[0].analysis_units[0].combined_content = "tampered"

    with pytest.raises(ValueError, match="analysis unit fields do not match source messages"):
        validate_cleaned_chat(result)


def test_statistics_do_not_accumulate_between_runs() -> None:
    first = rich_result()
    second = rich_result()

    assert first.statistics == second.statistics

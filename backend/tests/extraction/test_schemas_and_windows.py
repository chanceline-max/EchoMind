"""Strict request, output schema, context, and window contracts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from echomind.extraction.context import ContextMessage
from echomind.extraction.fingerprints import insight_fingerprint
from echomind.extraction.options import ExtractionRequest
from echomind.extraction.schemas import CandidateInsightBatch
from echomind.extraction.windows import TRUNCATION_MARKER, build_windows
from tests.extraction.factories import candidate


def test_request_deduplicates_conversations_without_reordering() -> None:
    first, second = uuid4(), uuid4()
    request = ExtractionRequest(conversation_ids=[first, second, first])
    assert request.conversation_ids == [first, second]


@pytest.mark.parametrize(
    ("updates", "location"),
    [
        ({"conversation_ids": []}, "conversation_ids"),
        ({"start_at": datetime(2026, 1, 1)}, "start_at"),
        ({"overlap_messages": 40}, ""),
        ({"max_single_message_characters": 101, "max_window_characters": 100}, ""),
    ],
)
def test_invalid_request_is_rejected(updates: dict[str, object], location: str) -> None:
    values: dict[str, object] = {"conversation_ids": [uuid4()]}
    values.update(updates)
    with pytest.raises(ValidationError) as error:
        ExtractionRequest.model_validate(values)
    assert location in str(error.value)


def test_request_rejects_reversed_time_range() -> None:
    with pytest.raises(ValidationError):
        ExtractionRequest(
            conversation_ids=[uuid4()],
            start_at=datetime(2026, 2, 1, tzinfo=UTC),
            end_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("insight_type", "unsupported"),
        ("category", "unbounded"),
        ("model_confidence", 1.1),
        ("title", "x" * 256),
        ("statement", "x" * 2001),
    ],
)
def test_candidate_schema_rejects_invalid_values(field: str, value: object) -> None:
    payload = candidate()
    payload[field] = value
    with pytest.raises(ValidationError):
        CandidateInsightBatch.model_validate({"candidates": [payload]}, strict=True)


def test_candidate_schema_rejects_extra_and_model_excerpt() -> None:
    payload = candidate(extra_value=True)
    payload["evidence_refs"][0]["excerpt"] = "forbidden"
    with pytest.raises(ValidationError):
        CandidateInsightBatch.model_validate({"candidates": [payload]}, strict=True)


def _messages(count: int, size: int = 10) -> list[ContextMessage]:
    return [
        ContextMessage(
            database_message_id=str(uuid4()),
            conversation_id="conversation-db-id",
            sender_id=f"sender-{index % 2}",
            is_profile_owner=index % 2 == 0,
            timestamp=datetime(2026, 1, index + 1, tzinfo=UTC),
            message_type="text",
            normalized_content=str(index) * size,
            reply_to_message_id=None,
            source_order=index,
        )
        for index in range(count)
    ]


def test_windows_split_by_message_count_with_overlap_and_no_empty_tail() -> None:
    request = ExtractionRequest(
        conversation_ids=[uuid4()],
        max_window_messages=3,
        overlap_messages=1,
    )
    windows = build_windows(_messages(5), request)
    assert [len(item.messages) for item in windows] == [3, 3]
    assert windows[0].messages[-1].database_message_id == windows[1].messages[0].database_message_id


def test_windows_split_by_character_count_and_truncate_deterministically() -> None:
    request = ExtractionRequest(
        conversation_ids=[uuid4()],
        max_window_messages=5,
        max_window_characters=64,
        max_single_message_characters=32,
        overlap_messages=0,
    )
    source = _messages(3, 80)
    first = build_windows(source, request)
    second = build_windows(source, request)
    assert [item.window_id for item in first] == [item.window_id for item in second]
    assert [len(item.messages) for item in first] == [2, 1]
    assert first[0].messages[0].normalized_content.endswith(TRUNCATION_MARKER)
    assert len(first[0].messages[0].normalized_content) == 32
    assert source[0].normalized_content == "0" * 80


def test_window_id_does_not_depend_on_content() -> None:
    request = ExtractionRequest(conversation_ids=[uuid4()])
    original = _messages(2)
    changed = _messages(2)
    for source, target in zip(original, changed, strict=True):
        target.database_message_id = source.database_message_id
        target.normalized_content = "changed"
    assert (
        build_windows(original, request)[0].window_id
        == build_windows(changed, request)[0].window_id
    )


def test_insight_fingerprint_is_conservative_and_stable() -> None:
    first = insight_fingerprint(
        extraction_version="candidate-extraction-1.1",
        insight_type="fact",
        category="background",
        statement="  A   Synthetic\nStatement ",
        valid_from=None,
        valid_to=None,
    )
    second = insight_fingerprint(
        extraction_version="candidate-extraction-1.1",
        insight_type="fact",
        category="background",
        statement="A Synthetic Statement",
        valid_from=None,
        valid_to=None,
    )
    case_changed = insight_fingerprint(
        extraction_version="candidate-extraction-1.1",
        insight_type="fact",
        category="background",
        statement="a synthetic statement",
        valid_from=None,
        valid_to=None,
    )
    assert first == second
    assert first != case_changed

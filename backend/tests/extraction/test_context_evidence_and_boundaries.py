"""Additional selection, alias, Evidence, prompt, and limit boundaries."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from echomind.extraction.candidate_validation import validate_candidate
from echomind.extraction.context import select_context
from echomind.extraction.errors import ExtractionError
from echomind.extraction.evidence import MAX_EVIDENCE_CHARACTERS, bind_evidence
from echomind.extraction.options import ExtractionRequest
from echomind.extraction.prompts import SYSTEM_INSTRUCTION
from echomind.extraction.schemas import CandidateInsightBatch
from echomind.extraction.service import extract_candidates
from echomind.extraction.windows import TRUNCATION_MARKER, build_windows
from tests.extraction.factories import (
    ScriptedProvider,
    candidate,
    create_chat,
    evidence_ref,
    session_factory_for,
)


def test_time_range_and_archived_message_selection(db_session: Session) -> None:
    conversation, _, messages = create_chat(db_session)
    messages[2].archived_at = datetime(2026, 2, 1, tzinfo=UTC)
    db_session.commit()
    request = ExtractionRequest(
        conversation_ids=[UUID(conversation.id)],
        start_at=datetime(2026, 1, 2, tzinfo=UTC),
        end_at=datetime(2026, 1, 4, 23, 59, tzinfo=UTC),
    )
    selection = select_context(db_session, request)
    assert [item.database_message_id for item in selection.conversations[0].messages] == [
        messages[1].id,
        messages[3].id,
    ]
    assert selection.excluded_message_count == 1


def test_only_explicit_conversations_are_selected_in_request_order(db_session: Session) -> None:
    first, _, first_messages = create_chat(db_session, conversation_suffix="1")
    second, _, second_messages = create_chat(db_session, conversation_suffix="2")
    request = ExtractionRequest(
        conversation_ids=[UUID(second.id), UUID(first.id)],
    )
    selection = select_context(db_session, request)
    assert [item.conversation_id for item in selection.conversations] == [second.id, first.id]
    assert selection.conversations[0].messages[0].database_message_id == second_messages[0].id
    assert selection.conversations[1].messages[0].database_message_id == first_messages[0].id


def test_multi_conversation_windows_are_never_mixed(db_session: Session) -> None:
    first, _, _ = create_chat(db_session, conversation_suffix="1", messages=2)
    second, _, _ = create_chat(db_session, conversation_suffix="2", messages=2)
    provider = ScriptedProvider([{"candidates": []}, {"candidates": []}])
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(conversation_ids=[UUID(first.id), UUID(second.id)]),
        provider=provider,
    )
    assert report.window_count == 2
    assert [item.conversation_id for item in report.window_results] == [first.id, second.id]
    assert all(item.metadata_json["conversation_count"] == 1 for item in provider.requests)


def test_no_analyzable_messages_is_controlled(db_session: Session) -> None:
    conversation, _, messages = create_chat(db_session)
    for message in messages:
        message.excluded_from_analysis = True
    db_session.commit()
    with pytest.raises(ExtractionError) as error:
        extract_candidates(
            session_factory_for(db_session),
            ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
            provider=ScriptedProvider([]),
        )
    assert error.value.error_code.value == "no_analyzable_messages"


def test_reply_alias_is_local_and_missing_target_is_omitted(db_session: Session) -> None:
    conversation, _, messages = create_chat(db_session, messages=3)
    messages[1].reply_to_message_id = messages[0].id
    messages[2].reply_to_message_id = messages[0].id
    db_session.commit()
    selection = select_context(
        db_session,
        ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
    )
    request = ExtractionRequest(
        conversation_ids=[UUID(conversation.id)],
        max_window_messages=2,
        overlap_messages=0,
    )
    windows = build_windows(selection.conversations[0].messages, request)
    first_payload = windows[0].messages[1].provider_dict()
    second_payload = windows[1].messages[0].provider_dict()
    assert first_payload["reply_to_context_message_id"] == "m001"
    assert "reply_to_context_message_id" not in second_payload
    assert messages[0].id not in str(second_payload)


def test_other_participant_aliases_are_stable_and_anonymous(db_session: Session) -> None:
    conversation, participants, _ = create_chat(db_session)
    provider = ScriptedProvider([{"candidates": []}])
    extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
        provider=provider,
    )
    payload = provider.requests[0].user_content[0].content
    assert "PROFILE_OWNER" in payload
    assert "OTHER_1" in payload
    assert all(item.canonical_name not in payload for item in participants)


def test_evidence_excerpt_is_bounded_stable_and_role_sensitive() -> None:
    request = ExtractionRequest(
        conversation_ids=[uuid4()],
        max_window_characters=1_000,
        max_single_message_characters=1_000,
    )
    from tests.extraction.test_schemas_and_windows import _messages

    source = _messages(1, 800)
    window = build_windows(source, request)[0]
    supporting = (
        CandidateInsightBatch.model_validate({"candidates": [candidate()]}, strict=True)
        .candidates[0]
        .evidence_refs[0]
    )
    contextual = (
        CandidateInsightBatch.model_validate(
            {"candidates": [candidate(refs=[evidence_ref("m001", "contextual")])]},
            strict=True,
        )
        .candidates[0]
        .evidence_refs[0]
    )
    first = bind_evidence(supporting, window.messages[0])
    repeated = bind_evidence(supporting, window.messages[0])
    other_role = bind_evidence(contextual, window.messages[0])
    assert len(first.excerpt) == MAX_EVIDENCE_CHARACTERS
    assert first.excerpt.endswith(TRUNCATION_MARKER)
    assert first == repeated
    assert first.evidence_fingerprint != other_role.evidence_fingerprint


def test_different_messages_have_different_evidence_fingerprints() -> None:
    request = ExtractionRequest(conversation_ids=[uuid4()])
    from tests.extraction.test_schemas_and_windows import _messages

    window = build_windows(_messages(2), request)[0]
    reference = (
        CandidateInsightBatch.model_validate({"candidates": [candidate()]}, strict=True)
        .candidates[0]
        .evidence_refs[0]
    )
    first = bind_evidence(reference, window.messages[0])
    second = bind_evidence(reference, window.messages[1])
    assert first.evidence_fingerprint != second.evidence_fingerprint


def test_candidate_batch_respects_request_specific_limit(db_session: Session) -> None:
    conversation, _, _ = create_chat(db_session)
    provider = ScriptedProvider(
        [{"candidates": [candidate(), candidate(statement="Second candidate.")]}]
    )
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(
            conversation_ids=[UUID(conversation.id)],
            max_candidates_per_window=1,
        ),
        provider=provider,
    )
    assert report.failed_window_count == 1
    assert report.errors[0].error_code == "candidate_batch_invalid"


def test_schema_absolute_candidate_limit() -> None:
    with pytest.raises(ValidationError):
        CandidateInsightBatch.model_validate(
            {"candidates": [candidate(statement=f"Candidate {index}") for index in range(51)]},
            strict=True,
        )


def test_pattern_same_timestamp_is_rejected() -> None:
    from tests.extraction.test_candidate_validation import window

    current = window()
    current.messages[2] = current.messages[2].__class__(
        **{
            **current.messages[2].__dict__,
            "timestamp": current.messages[0].timestamp,
        }
    )
    parsed = CandidateInsightBatch.model_validate(
        {
            "candidates": [
                candidate(
                    insight_type="pattern",
                    refs=[evidence_ref("m001"), evidence_ref("m003")],
                    explicit=False,
                )
            ]
        },
        strict=True,
    ).candidates[0]
    with pytest.raises(ExtractionError) as error:
        validate_candidate(parsed, current, candidate_index=0)
    assert error.value.details["rule"] == "pattern_distinct_times"


def test_preference_accepts_two_owner_messages_without_explicit_report() -> None:
    from tests.extraction.test_candidate_validation import window

    parsed = CandidateInsightBatch.model_validate(
        {
            "candidates": [
                candidate(
                    insight_type="preference",
                    refs=[evidence_ref("m001"), evidence_ref("m003")],
                    explicit=False,
                )
            ]
        },
        strict=True,
    ).candidates[0]
    assert validate_candidate(parsed, window(), candidate_index=0) is not None


def test_empty_evidence_content_is_rejected_safely() -> None:
    from tests.extraction.test_candidate_validation import window

    current = window()
    current.messages[0] = current.messages[0].__class__(
        **{**current.messages[0].__dict__, "evidence_content": ""}
    )
    parsed = CandidateInsightBatch.model_validate(
        {"candidates": [candidate()]}, strict=True
    ).candidates[0]
    with pytest.raises(ExtractionError) as error:
        validate_candidate(parsed, current, candidate_index=0)
    assert error.value.details["rule"] == "evidence_content_non_empty"


def test_prompt_contains_required_safety_constraints() -> None:
    normalized = SYSTEM_INSTRUCTION.casefold()
    for required in [
        "profile_owner",
        "single message",
        "medical or psychological diagnoses",
        "mbti",
        "outside the supplied window",
        "only json",
    ]:
        assert required in normalized


def test_default_mock_pipeline_returns_empty_candidates_without_network(
    db_session: Session,
) -> None:
    conversation, _, _ = create_chat(db_session)
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
    )
    assert report.successful_window_count == 1
    assert report.candidates_received == 0

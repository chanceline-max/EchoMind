"""End-to-end in-process extraction, privacy, persistence, and recovery tests."""

import json
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from echomind.extraction.errors import ExtractionError
from echomind.extraction.options import ExtractionRequest
from echomind.extraction.service import extract_candidates
from echomind.models import Evidence, Insight, InsightEvidence
from echomind.models.enums import InsightStatus
from echomind.providers import ProviderError, ProviderErrorCode
from tests.extraction.factories import (
    REQUEST_ID,
    ScriptedProvider,
    candidate,
    create_chat,
    evidence_ref,
    session_factory_for,
)


def test_context_privacy_selection_and_local_evidence(db_session: Session) -> None:
    conversation, participants, messages = create_chat(db_session)
    messages[1].excluded_from_analysis = True
    db_session.commit()
    provider = ScriptedProvider([{"candidates": [candidate()]}])
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(request_id=REQUEST_ID, conversation_ids=[UUID(conversation.id)]),
        provider=provider,
    )
    payload = provider.requests[0]
    serialized = payload.model_dump_json()
    context = json.loads(payload.user_content[0].content)

    assert report.selected_message_count == 3
    assert report.excluded_message_count == 1
    assert [item["context_message_id"] for item in context["messages"]] == ["m001", "m002", "m003"]
    assert context["messages"][0]["sender_role"] == "PROFILE_OWNER"
    assert context["messages"][1]["sender_role"] == "PROFILE_OWNER"
    for forbidden in [
        messages[0].raw_content,
        messages[0].source_message_id,
        messages[0].id,
        participants[0].canonical_name,
        "METADATA_PRIVATE",
        "CLEANING_PRIVATE",
        "synthetic-1.json",
    ]:
        assert forbidden not in serialized
    evidence = db_session.scalar(select(Evidence))
    assert evidence is not None
    assert evidence.excerpt.startswith("Synthetic normalized")
    assert "RAW_PRIVATE" not in evidence.excerpt
    assert evidence.is_valid is True


def test_repeat_run_is_idempotent_and_preserves_user_state(db_session: Session) -> None:
    conversation, _, _ = create_chat(db_session)
    payload = {"candidates": [candidate()]}
    request = ExtractionRequest(
        request_id=REQUEST_ID,
        conversation_ids=[UUID(conversation.id)],
    )
    first = extract_candidates(
        session_factory_for(db_session), request, provider=ScriptedProvider([payload])
    )
    insight = db_session.scalar(select(Insight))
    assert insight is not None
    insight.title = "User edited title"
    insight.statement = "User edited statement"
    insight.status = InsightStatus.REJECTED
    db_session.commit()
    second = extract_candidates(
        session_factory_for(db_session), request, provider=ScriptedProvider([payload])
    )
    db_session.refresh(insight)

    assert first.insights_created == 1
    assert second.insights_reused == 1
    assert db_session.scalar(select(func.count()).select_from(Insight)) == 1
    assert db_session.scalar(select(func.count()).select_from(Evidence)) == 1
    assert db_session.scalar(select(func.count()).select_from(InsightEvidence)) == 1
    assert insight.title == "User edited title"
    assert insight.statement == "User edited statement"
    assert insight.status is InsightStatus.REJECTED
    assert insight.confidence == 0.0
    assert insight.confidence_version == "unscored"
    assert insight.model_confidence == 0.8
    assert insight.provider_name == "mock"


def test_existing_insight_can_receive_new_evidence(db_session: Session) -> None:
    conversation, _, _ = create_chat(db_session)
    request = ExtractionRequest(
        request_id=REQUEST_ID,
        conversation_ids=[UUID(conversation.id)],
    )
    first_payload = {"candidates": [candidate()]}
    second_payload = {"candidates": [candidate(refs=[evidence_ref("m001"), evidence_ref("m003")])]}
    extract_candidates(
        session_factory_for(db_session), request, provider=ScriptedProvider([first_payload])
    )
    report = extract_candidates(
        session_factory_for(db_session), request, provider=ScriptedProvider([second_payload])
    )
    assert report.insights_reused == 1
    assert db_session.scalar(select(func.count()).select_from(Insight)) == 1
    assert db_session.scalar(select(func.count()).select_from(Evidence)) == 2
    assert db_session.scalar(select(func.count()).select_from(InsightEvidence)) == 2


@pytest.mark.parametrize(
    ("owner_count", "error_code"),
    [(0, "profile_owner_not_identified"), (2, "multiple_profile_owners")],
)
def test_profile_owner_errors(db_session: Session, owner_count: int, error_code: str) -> None:
    conversation, _, _ = create_chat(db_session, owner_count=owner_count)
    with pytest.raises(ExtractionError) as error:
        extract_candidates(
            session_factory_for(db_session),
            ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
            provider=ScriptedProvider([]),
        )
    assert error.value.error_code.value == error_code


def test_archived_and_missing_conversations_fail_safely(db_session: Session) -> None:
    archived, _, _ = create_chat(db_session, archived=True)
    with pytest.raises(ExtractionError) as archived_error:
        extract_candidates(
            session_factory_for(db_session),
            ExtractionRequest(conversation_ids=[UUID(archived.id)]),
            provider=ScriptedProvider([]),
        )
    assert archived_error.value.error_code.value == "conversation_archived"


def test_partial_candidate_rejection_does_not_block_valid_candidate(db_session: Session) -> None:
    conversation, _, _ = create_chat(db_session)
    provider = ScriptedProvider(
        [{"candidates": [candidate(explicit=False), candidate(statement="A valid candidate.")]}]
    )
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
        provider=provider,
    )
    assert (report.candidates_received, report.candidates_accepted, report.candidates_rejected) == (
        2,
        1,
        1,
    )
    assert db_session.scalar(select(func.count()).select_from(Insight)) == 1


@pytest.mark.parametrize("stop", [True, False])
def test_window_failure_stop_policy_preserves_prior_commits(
    db_session: Session, stop: bool
) -> None:
    conversation, _, _ = create_chat(db_session, messages=5)
    failure = ProviderError(
        ProviderErrorCode.TIMEOUT,
        message="Synthetic timeout.",
        provider_name="mock",
        recoverable=True,
    )
    provider = ScriptedProvider(
        [
            {"candidates": [candidate()]},
            failure,
            {"candidates": [candidate(statement="Third synthetic insight.")]},
        ]
    )
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(
            conversation_ids=[UUID(conversation.id)],
            max_window_messages=2,
            overlap_messages=0,
            stop_on_window_error=stop,
        ),
        provider=provider,
    )
    assert report.failed_window_count == 1
    assert report.stopped_early is stop
    expected = 1 if stop else 2
    assert db_session.scalar(select(func.count()).select_from(Insight)) == expected
    assert len(provider.requests) == (2 if stop else 3)


def test_report_and_errors_do_not_contain_sensitive_content(db_session: Session) -> None:
    conversation, participants, messages = create_chat(db_session)
    failure = ProviderError(
        ProviderErrorCode.TIMEOUT,
        message="Synthetic timeout.",
        provider_name="mock",
        recoverable=True,
    )
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
        provider=ScriptedProvider([failure]),
    )
    serialized = report.model_dump_json()
    assert messages[0].raw_content not in serialized
    assert messages[0].normalized_content not in serialized
    assert participants[0].canonical_name not in serialized


def test_report_counts_overlapped_truncated_message_once(db_session: Session) -> None:
    conversation, _, _ = create_chat(db_session, messages=4, content_size=80)
    report = extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(
            conversation_ids=[UUID(conversation.id)],
            max_window_messages=3,
            max_window_characters=96,
            max_single_message_characters=32,
            overlap_messages=1,
        ),
        provider=ScriptedProvider([{"candidates": []}, {"candidates": []}]),
    )
    assert report.window_count == 2
    assert sum(item.truncated_message_count for item in report.window_results) == 5
    assert report.truncated_message_count == 4

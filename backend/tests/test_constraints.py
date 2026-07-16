"""Database constraints that protect provenance and evidence integrity."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from echomind.models import (
    Conversation,
    Evidence,
    Insight,
    InsightEvidence,
    Message,
    conversation_participants,
)
from echomind.models.enums import InsightType, MessageType
from tests.db_helpers import create_evidence_graph, make_source


def assert_integrity_error(session: Session, operation: Callable[[], object]) -> None:
    with pytest.raises(IntegrityError):
        operation()
        session.flush()
    session.rollback()


def test_source_file_hash_is_globally_unique(db_session: Session) -> None:
    db_session.add(make_source("c" * 64))
    db_session.commit()

    assert_integrity_error(db_session, lambda: db_session.add(make_source("c" * 64)))


def test_source_message_id_is_unique_only_within_a_conversation(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    duplicate = Message(
        conversation_id=graph.conversation.id,
        source_message_id=graph.message.source_message_id,
        sender_id=graph.participant.id,
        sequence_index=1,
        message_type=MessageType.TEXT,
        raw_content="Different synthetic text",
        normalized_content="Different synthetic text",
    )

    assert_integrity_error(db_session, lambda: db_session.add(duplicate))


def test_different_conversations_can_reuse_source_message_id(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    second_conversation = Conversation(
        source_file_id=graph.source_file.id,
        platform="synthetic",
        source_conversation_id="conversation-2",
    )
    second_message = Message(
        conversation=second_conversation,
        source_message_id=graph.message.source_message_id,
        sender=graph.participant,
        sequence_index=0,
        message_type=MessageType.TEXT,
        raw_content="A separate synthetic conversation.",
        normalized_content="A separate synthetic conversation.",
    )
    db_session.add_all([second_conversation, second_message])
    db_session.flush()
    db_session.execute(
        conversation_participants.insert().values(
            conversation_id=second_conversation.id,
            participant_id=graph.participant.id,
        )
    )
    db_session.commit()

    assert second_message.id != graph.message.id


def test_insight_evidence_link_cannot_be_duplicated(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)

    assert_integrity_error(
        db_session,
        lambda: db_session.execute(
            insert(InsightEvidence).values(
                insight_id=graph.insight.id,
                evidence_id=graph.evidence.id,
            )
        ),
    )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_insight_confidence_must_be_in_range(
    db_session: Session,
    confidence: float,
) -> None:
    insight = Insight(
        category="synthetic",
        insight_type=InsightType.FACT,
        title="Invalid score",
        statement="Synthetic invalid score",
        confidence=confidence,
        extraction_version="test-v1",
    )

    assert_integrity_error(db_session, lambda: db_session.add(insight))


def test_evidence_excerpt_offsets_must_form_positive_range(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    invalid = Evidence(
        message_id=graph.message.id,
        excerpt="invalid",
        excerpt_start=8,
        excerpt_end=8,
        excerpt_hash="d" * 64,
        evidence_type="synthetic",
        relevance_score=0.5,
    )

    assert_integrity_error(db_session, lambda: db_session.add(invalid))


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_evidence_relevance_must_be_in_range(db_session: Session, score: float) -> None:
    graph = create_evidence_graph(db_session)
    invalid = Evidence(
        message_id=graph.message.id,
        excerpt="invalid score",
        excerpt_start=0,
        excerpt_end=13,
        excerpt_hash="f" * 64,
        evidence_type="synthetic",
        relevance_score=score,
    )

    assert_integrity_error(db_session, lambda: db_session.add(invalid))


def test_conversation_time_range_is_enforced(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    invalid = Conversation(
        source_file_id=graph.source_file.id,
        platform="synthetic",
        source_conversation_id="invalid-time",
        started_at=graph.message.timestamp,
        ended_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    assert_integrity_error(db_session, lambda: db_session.add(invalid))


def test_insight_valid_time_range_is_enforced(db_session: Session) -> None:
    invalid = Insight(
        category="synthetic",
        insight_type=InsightType.CHANGE,
        title="Invalid range",
        statement="Synthetic invalid time range.",
        confidence=0.5,
        valid_from=datetime(2026, 1, 2, tzinfo=UTC),
        valid_to=datetime(2026, 1, 1, tzinfo=UTC),
        extraction_version="test-v1",
    )

    assert_integrity_error(db_session, lambda: db_session.add(invalid))


def test_unknown_message_foreign_key_is_rejected(db_session: Session) -> None:
    invalid = Evidence(
        message_id="00000000-0000-4000-8000-000000000000",
        excerpt="invalid",
        excerpt_start=0,
        excerpt_end=7,
        excerpt_hash="e" * 64,
        evidence_type="synthetic",
        relevance_score=0.5,
    )

    assert_integrity_error(db_session, lambda: db_session.add(invalid))

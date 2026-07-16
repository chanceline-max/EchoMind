"""Core model persistence and relationship tests."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from echomind.models import Message, ProfileSnapshot
from echomind.models.enums import EvidenceState, MessageType
from tests.db_helpers import create_evidence_graph


def test_complete_evidence_graph_round_trips_without_changing_raw_content(
    db_session: Session,
) -> None:
    graph = create_evidence_graph(db_session)
    db_session.expire_all()

    message = db_session.scalar(select(Message).where(Message.id == graph.message.id))

    assert message is not None
    assert UUID(message.id).version == 4
    assert message.raw_content == "I enjoy making small tools."
    assert message.normalized_content == "I enjoy making small tools."
    assert message.evidences[0].insight_links[0].insight.statement.startswith("The user")
    assert message.conversation.participants[0].canonical_name == "Example Person"


def test_normalized_content_can_change_without_touching_raw_content(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    graph.message.normalized_content = "I enjoy making tools."
    db_session.commit()
    db_session.refresh(graph.message)

    assert graph.message.raw_content == "I enjoy making small tools."
    assert graph.message.normalized_content == "I enjoy making tools."


def test_message_reply_relationship_round_trips(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    reply = Message(
        conversation_id=graph.conversation.id,
        source_message_id="message-2",
        sender_id=graph.participant.id,
        timestamp=datetime(2026, 1, 2, 3, 5, tzinfo=UTC),
        sequence_index=1,
        message_type=MessageType.TEXT,
        raw_content="A synthetic reply.",
        normalized_content="A synthetic reply.",
        reply_to=graph.message,
    )
    db_session.add(reply)
    db_session.commit()
    db_session.refresh(reply)

    assert reply.reply_to is graph.message
    assert reply in graph.message.replies


def test_profile_snapshot_preserves_structured_content(db_session: Session) -> None:
    snapshot = ProfileSnapshot(
        profile_version="profile-v1",
        schema_version="schema-v1",
        markdown_content="# Synthetic profile",
        json_content={"summary": "synthetic"},
        statistics={"insight_count": 1},
        limitations=["Synthetic test only"],
        evidence_state=EvidenceState.VALID,
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)

    assert snapshot.json_content == {"summary": "synthetic"}
    assert snapshot.limitations == ["Synthetic test only"]


def test_sqlite_foreign_keys_are_enabled(db_session: Session) -> None:
    enabled = db_session.execute(text("PRAGMA foreign_keys")).scalar_one()
    assert enabled == 1

"""UTC normalization and naive-datetime rejection tests."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from echomind.models import Message
from echomind.models.enums import MessageType
from tests.db_helpers import create_evidence_graph


def test_non_utc_datetime_is_normalized_and_read_as_aware_utc(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    original = datetime(2026, 2, 3, 12, 0, tzinfo=timezone(timedelta(hours=8)))
    message = Message(
        conversation_id=graph.conversation.id,
        source_message_id="offset-message",
        sender_id=graph.participant.id,
        timestamp=original,
        sequence_index=2,
        message_type=MessageType.TEXT,
        raw_content="Synthetic offset timestamp",
        normalized_content="Synthetic offset timestamp",
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    assert message.timestamp == datetime(2026, 2, 3, 4, 0, tzinfo=UTC)
    assert message.timestamp is not None
    assert message.timestamp.utcoffset() == timedelta(0)


def test_naive_datetime_is_rejected_before_storage(db_session: Session) -> None:
    graph = create_evidence_graph(db_session)
    message = Message(
        conversation_id=graph.conversation.id,
        source_message_id="naive-message",
        sender_id=graph.participant.id,
        timestamp=datetime(2026, 2, 3, 12, 0),
        sequence_index=2,
        message_type=MessageType.TEXT,
        raw_content="Synthetic naive timestamp",
        normalized_content="Synthetic naive timestamp",
    )
    db_session.add(message)

    with pytest.raises(StatementError, match="naive datetime"):
        db_session.flush()
    db_session.rollback()

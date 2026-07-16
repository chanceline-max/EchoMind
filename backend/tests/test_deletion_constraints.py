"""Deletion attempts must not silently break the provenance chain."""

from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from echomind.models import (
    Conversation,
    Evidence,
    Insight,
    Message,
    Participant,
    SourceFile,
    conversation_participants,
)
from tests.db_helpers import EvidenceGraph, create_evidence_graph, make_source


def assert_delete_is_restricted(
    session: Session,
    graph: EvidenceGraph,
    load_target: Callable[[EvidenceGraph], object],
) -> None:
    session.expire_all()
    session.delete(load_target(graph))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(
    "loader",
    [
        lambda graph: graph.source_file,
        lambda graph: graph.conversation,
        lambda graph: graph.message,
        lambda graph: graph.evidence,
        lambda graph: graph.insight,
    ],
    ids=["source-file", "conversation", "message", "evidence", "insight"],
)
def test_evidence_chain_deletions_are_restricted(
    db_session: Session,
    loader: Callable[[EvidenceGraph], object],
) -> None:
    graph = create_evidence_graph(db_session)
    assert_delete_is_restricted(db_session, graph, loader)

    assert db_session.scalar(select(func.count()).select_from(SourceFile)) == 1
    assert db_session.scalar(select(func.count()).select_from(Message)) == 1
    assert db_session.scalar(select(func.count()).select_from(Evidence)) == 1
    assert db_session.scalar(select(func.count()).select_from(Insight)) == 1
    assert db_session.scalar(select(func.count()).select_from(Conversation)) == 1


def test_loaded_participant_relationship_does_not_bypass_restrict(db_session: Session) -> None:
    source_file = make_source()
    participant = Participant(canonical_name="Association Test Person")
    conversation = Conversation(
        source_file=source_file,
        platform="synthetic",
        source_conversation_id="association-only",
    )
    db_session.add_all([source_file, participant, conversation])
    db_session.flush()
    db_session.execute(
        conversation_participants.insert().values(
            conversation_id=conversation.id,
            participant_id=participant.id,
        )
    )
    db_session.commit()
    db_session.expire_all()

    assert conversation.participants == [participant]
    db_session.delete(conversation)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    assert db_session.get(Conversation, conversation.id) is not None

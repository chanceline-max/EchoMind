"""Stage 11 proof that a rendered Profile claim remains source-traceable."""

from typing import cast

from sqlalchemy import Engine
from sqlalchemy.orm import Session
from tests.profiling.factories import create_profile_graph, profile_request

from echomind.core.config import Settings
from echomind.db.session import create_session_factory
from echomind.models import Conversation, Evidence, Insight, InsightEvidence, Message, SourceFile
from echomind.profiling.service import generate_profile, read_document


def test_profile_insight_traces_to_evidence_message_conversation_and_source(
    db_session: Session, settings: Settings
) -> None:
    create_profile_graph(db_session)
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    snapshot, created = generate_profile(factory, profile_request(), settings=settings)
    assert created is True
    document = read_document(snapshot)
    item = next(section.items[0] for section in document.sections if section.items)

    insight = db_session.get(Insight, item.insight_id)
    assert insight is not None
    assert insight.revision_number == item.insight_revision_number
    assert item.evidence_refs
    indexed = {entry.profile_evidence_ref: entry for entry in document.evidence_index}
    for reference in item.evidence_refs:
        profile_evidence = indexed[reference]
        evidence = db_session.get(Evidence, profile_evidence.evidence_id)
        assert evidence is not None
        assert db_session.get(InsightEvidence, (insight.id, evidence.id)) is not None
        assert evidence.message_id == profile_evidence.message_id
        message = db_session.get(Message, evidence.message_id)
        assert message is not None
        conversation = db_session.get(Conversation, message.conversation_id)
        assert conversation is not None
        assert conversation.id == profile_evidence.conversation_id
        source = db_session.get(SourceFile, conversation.source_file_id)
        assert source is not None
        assert len(source.file_hash) == 64

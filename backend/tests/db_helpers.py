"""Synthetic, privacy-safe model factories used by database tests."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from echomind.models import (
    Conversation,
    Evidence,
    Insight,
    InsightEvidence,
    Message,
    Participant,
    SourceFile,
    conversation_participants,
)
from echomind.models.enums import EvidenceStance, FileType, InsightType, MessageType


@dataclass
class EvidenceGraph:
    source_file: SourceFile
    conversation: Conversation
    participant: Participant
    message: Message
    evidence: Evidence
    insight: Insight
    link: InsightEvidence


def make_source(file_hash: str = "a" * 64) -> SourceFile:
    return SourceFile(
        filename="synthetic-chat.json",
        file_type=FileType.JSON,
        file_hash=file_hash,
        byte_size=128,
        parser_name="synthetic-parser",
        parser_version="1.0.0",
    )


def create_evidence_graph(session: Session) -> EvidenceGraph:
    """Persist one complete source-to-insight chain using invented text."""

    source_file = make_source()
    conversation = Conversation(
        source_file=source_file,
        platform="synthetic",
        source_conversation_id="conversation-1",
    )
    participant = Participant(canonical_name="Example Person", is_profile_owner=True)
    message = Message(
        conversation=conversation,
        source_message_id="message-1",
        sender=participant,
        timestamp=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        sequence_index=0,
        message_type=MessageType.TEXT,
        raw_content="I enjoy making small tools.",
        normalized_content="I enjoy making small tools.",
    )
    evidence = Evidence(
        message=message,
        excerpt="enjoy making small tools",
        excerpt_start=2,
        excerpt_end=26,
        excerpt_hash="b" * 64,
        evidence_type="explicit_statement",
        stance=EvidenceStance.SUPPORTS,
        relevance_score=0.9,
    )
    insight = Insight(
        category="interests",
        insight_type=InsightType.FACT,
        title="Enjoys making tools",
        statement="The user explicitly said they enjoy making small tools.",
        confidence=0.9,
        extraction_version="rules-v1",
    )
    link = InsightEvidence(insight=insight, evidence=evidence)
    session.add_all([source_file, conversation, participant, message, evidence, insight, link])
    session.flush()
    session.execute(
        conversation_participants.insert().values(
            conversation_id=conversation.id,
            participant_id=participant.id,
        )
    )
    session.commit()
    return EvidenceGraph(source_file, conversation, participant, message, evidence, insight, link)

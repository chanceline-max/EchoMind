"""Synthetic review graphs that contain no real conversation content."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from echomind.models import Evidence, Insight, InsightEvidence, Message
from echomind.models.enums import EvidenceStance, EvidenceState, InsightStatus, InsightType
from tests.extraction.factories import create_chat


@dataclass(frozen=True)
class ReviewGraph:
    insights: list[Insight]
    evidence: list[Evidence]
    messages: list[Message]


def create_review_graph(
    session: Session,
    *,
    insight_count: int = 2,
    evidence_count: int = 2,
    status: InsightStatus = InsightStatus.PROPOSED,
    conversation_suffix: str = "1",
) -> ReviewGraph:
    """Create deterministic Insights linked to distinct owner messages."""

    _, _, messages = create_chat(
        session,
        conversation_suffix=conversation_suffix,
        messages=max(6, evidence_count * 2),
    )
    seed = int(conversation_suffix[-1]) * 1_000
    owner_messages = [message for index, message in enumerate(messages) if index % 2 == 0]
    evidence: list[Evidence] = []
    for index in range(evidence_count):
        excerpt = f"Synthetic review excerpt {index}."
        row = Evidence(
            message_id=owner_messages[index].id,
            excerpt=excerpt,
            excerpt_start=0,
            excerpt_end=len(excerpt),
            excerpt_hash=f"{seed + index + 101:064x}",
            evidence_type="supporting",
            stance=EvidenceStance.SUPPORTS,
            relevance_score=0.8,
            is_valid=True,
            evidence_fingerprint=f"{seed + index + 201:064x}",
        )
        session.add(row)
        evidence.append(row)
    session.flush()

    insights: list[Insight] = []
    for index in range(insight_count):
        insight = Insight(
            category="background" if index == 0 else "values",
            insight_type=InsightType.FACT if index == 0 else InsightType.PREFERENCE,
            title=f"Synthetic review title {index}",
            statement=f"Synthetic review statement {index}.",
            confidence=0.0,
            status=status,
            evidence_state=EvidenceState.VALID,
            extraction_version="candidate-extraction-1.0",
            insight_fingerprint=f"{seed + index + 301:064x}",
            model_confidence=0.8,
            confidence_version="unscored",
            explicit_self_report=True,
        )
        session.add(insight)
        session.flush()
        for item in evidence:
            session.add(InsightEvidence(insight_id=insight.id, evidence_id=item.id))
        insights.append(insight)
    session.commit()
    return ReviewGraph(insights=insights, evidence=evidence, messages=messages)

"""Synthetic, content-independent confidence fixtures."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from echomind.confidence.factors import EvidenceFeature, InsightFeatures
from echomind.models import Evidence, Insight, InsightEvidence
from echomind.models.enums import (
    EvidenceStance,
    EvidenceState,
    InsightStatus,
    InsightType,
)
from tests.extraction.factories import create_chat

AS_OF = datetime(2026, 7, 19, tzinfo=UTC)
CALCULATED_AT = datetime(2026, 7, 19, 1, tzinfo=UTC)


def evidence_feature(
    index: int = 0,
    *,
    stance: EvidenceStance = EvidenceStance.SUPPORTS,
    valid: bool = True,
    owner: bool = True,
    timestamp: datetime | None = None,
    conversation: str = "conversation-1",
    relevance: float = 0.8,
    **updates: Any,
) -> EvidenceFeature:
    value: dict[str, Any] = {
        "evidence_id": f"evidence-{index}",
        "evidence_fingerprint": f"{index + 1:064x}",
        "evidence_type": stance.value,
        "stance": stance,
        "relevance_score": relevance,
        "is_valid": valid,
        "invalidated_at": None if valid else datetime(2026, 7, 18, tzinfo=UTC),
        "message_id": f"message-{index}",
        "sender_id": "owner" if owner else f"other-{index}",
        "conversation_id": conversation,
        "timestamp": timestamp or datetime(2026, 7, 1, tzinfo=UTC) + timedelta(days=index % 10),
        "is_profile_owner": owner,
    }
    value.update(updates)
    return EvidenceFeature(**value)


def insight_features(
    *,
    insight_type: InsightType = InsightType.FACT,
    evidence: tuple[EvidenceFeature, ...] | None = None,
    explicit: bool = True,
    **updates: Any,
) -> InsightFeatures:
    value: dict[str, Any] = {
        "insight_id": "00000000-0000-4000-8000-000000000801",
        "insight_type": insight_type,
        "status": InsightStatus.PROPOSED,
        "evidence_state": EvidenceState.VALID,
        "explicit_self_report": explicit,
        "valid_from": None,
        "valid_to": None,
        "extraction_version": "candidate-extraction-1.0",
        "insight_fingerprint": "a" * 64,
        "model_confidence": 0.8,
        "confidence": 0.0,
        "confidence_version": "unscored",
        "confidence_input_fingerprint": None,
        "confidence_as_of": None,
        "confidence_calculated_at": None,
        "has_reasoning_basis": True,
        "has_alternative_explanations": True,
        "evidence": evidence if evidence is not None else (evidence_feature(),),
    }
    value.update(updates)
    return InsightFeatures(**value)


def create_confidence_graph(
    session: Session,
    *,
    insight_type: InsightType = InsightType.FACT,
    status: InsightStatus = InsightStatus.PROPOSED,
    explicit: bool = True,
    evidence_count: int = 1,
) -> tuple[Insight, list[Evidence]]:
    _, _, messages = create_chat(session, messages=max(4, evidence_count * 2))
    insight = Insight(
        category="background",
        insight_type=insight_type,
        title="Synthetic title marker",
        statement="Synthetic statement marker",
        confidence=0.0,
        status=status,
        evidence_state=EvidenceState.VALID,
        extraction_version="candidate-extraction-1.0",
        insight_fingerprint="b" * 64,
        model_confidence=0.8,
        confidence_version="unscored",
        explicit_self_report=explicit,
        reasoning_basis="Synthetic reasoning"
        if insight_type in {InsightType.INFERENCE, InsightType.HYPOTHESIS}
        else None,
        alternative_explanations=(
            ["Synthetic alternative"]
            if insight_type in {InsightType.INFERENCE, InsightType.HYPOTHESIS}
            else []
        ),
    )
    session.add(insight)
    session.flush()
    evidence_rows: list[Evidence] = []
    owner_messages = [item for index, item in enumerate(messages) if index % 2 == 0]
    for index in range(evidence_count):
        message = owner_messages[index]
        evidence = Evidence(
            message_id=message.id,
            excerpt=f"Synthetic excerpt {index}",
            excerpt_start=0,
            excerpt_end=len(f"Synthetic excerpt {index}"),
            excerpt_hash=f"{index + 10:064x}",
            evidence_type="supporting",
            stance=EvidenceStance.SUPPORTS,
            relevance_score=0.8,
            is_valid=True,
            evidence_fingerprint=f"{index + 20:064x}",
        )
        session.add(evidence)
        session.flush()
        session.add(InsightEvidence(insight_id=insight.id, evidence_id=evidence.id))
        evidence_rows.append(evidence)
    session.commit()
    return insight, evidence_rows

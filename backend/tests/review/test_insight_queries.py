"""Aggregate-safe Insight review filters and stable pagination."""

from typing import Any

from sqlalchemy.orm import Session

from echomind.models.enums import EvidenceStance, EvidenceState, InsightStatus, InsightType
from echomind.schemas.insight_review import InsightPage
from echomind.services.insight_review_service import list_insights
from tests.review.factories import create_review_graph


def query(db_session: Session, **updates: object) -> InsightPage:
    filters: dict[str, Any] = {
        "status": None,
        "insight_type": None,
        "category": None,
        "evidence_state": None,
        "min_confidence": None,
        "max_confidence": None,
        "conversation_id": None,
        "source_file_id": None,
        "has_contradicting_evidence": None,
        "review_bucket": None,
        "limit": 50,
        "offset": 0,
        "sort": "updated_at_desc",
    }
    filters.update(updates)
    return list_insights(db_session, **filters)


def test_every_list_filter_combines_without_duplicate_insights(db_session: Session) -> None:
    graph = create_review_graph(db_session)
    first, second = graph.insights
    first.confidence = 0.2
    second.confidence = 0.8
    second.status = InsightStatus.CONFIRMED
    graph.evidence[1].stance = EvidenceStance.CONTRADICTS
    db_session.commit()
    conversation_id = graph.messages[0].conversation_id
    source_file_id = graph.messages[0].conversation.source_file_id

    assert query(db_session, status=InsightStatus.PROPOSED).total == 1
    assert query(db_session, insight_type=InsightType.FACT).items[0].id == first.id
    assert query(db_session, category="values").items[0].id == second.id
    assert query(db_session, evidence_state=EvidenceState.VALID).total == 2
    assert query(db_session, min_confidence=0.7, max_confidence=0.9).items[0].id == second.id
    assert query(db_session, conversation_id=conversation_id).total == 2
    assert query(db_session, source_file_id=source_file_id).total == 2
    assert query(db_session, has_contradicting_evidence=True).total == 2
    assert (
        query(
            db_session,
            status=InsightStatus.CONFIRMED,
            insight_type=InsightType.PREFERENCE,
            category="values",
            min_confidence=0.7,
            has_contradicting_evidence=True,
        )
        .items[0]
        .id
        == second.id
    )

    page = query(db_session, limit=1, offset=0, sort="confidence_desc")
    assert page.total == 2
    assert len(page.items) == 1
    assert page.items[0].id == second.id
    assert page.items[0].evidence_count == 2


def test_review_buckets_use_strict_threshold_type_and_evidence_rules(
    db_session: Session,
) -> None:
    graph = create_review_graph(db_session)
    first, second = graph.insights
    first.confidence = 0.5
    second.confidence = 0.8
    db_session.commit()

    eligible = query(db_session, review_bucket="batch_eligible")
    manual = query(db_session, review_bucket="manual")
    assert [item.id for item in eligible.items] == [second.id]
    assert [item.id for item in manual.items] == [first.id]

    second.insight_type = InsightType.INFERENCE
    db_session.commit()
    assert query(db_session, review_bucket="batch_eligible").total == 0
    assert query(db_session, review_bucket="manual").total == 2

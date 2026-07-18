"""Message exclusion propagates without breaking evidence provenance."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from echomind.api.errors import ApiError
from echomind.models import Evidence, Insight
from echomind.models.enums import EvidenceState, InsightRevisionAction, InsightStatus
from echomind.models.insight_revision import InsightRevision
from echomind.services.evidence_validity_service import set_message_analysis_exclusion
from tests.review.factories import create_review_graph

NOW = datetime(2026, 7, 20, 10, tzinfo=UTC)


def fixed_clock() -> datetime:
    return NOW


@pytest.mark.parametrize("status", [InsightStatus.PROPOSED, InsightStatus.CONFIRMED])
def test_exclude_and_reinclude_propagate_atomically_and_idempotently(
    db_session: Session,
    status: InsightStatus,
) -> None:
    graph = create_review_graph(db_session, insight_count=1, status=status)
    insight = graph.insights[0]
    evidence = graph.evidence[0]
    message = graph.messages[0]
    message_id = message.id

    excluded = set_message_analysis_exclusion(
        db_session,
        message_id=message_id,
        excluded=True,
        clock=fixed_clock,
    )
    db_session.refresh(evidence)
    db_session.refresh(insight)
    assert excluded.excluded_from_analysis is True
    assert evidence.is_valid is False
    assert evidence.invalidation_reasons_json == ["source_message_excluded"]
    assert evidence.invalidated_at == NOW
    assert insight.evidence_state is EvidenceState.PARTIAL
    assert insight.confidence_version == "confidence-1.0"
    assert insight.revision_number == 1
    db_session.rollback()

    set_message_analysis_exclusion(
        db_session,
        message_id=message_id,
        excluded=True,
        clock=fixed_clock,
    )
    db_session.refresh(insight)
    assert insight.revision_number == 1
    db_session.rollback()

    restored = set_message_analysis_exclusion(
        db_session,
        message_id=message_id,
        excluded=False,
        clock=fixed_clock,
    )
    db_session.refresh(evidence)
    db_session.refresh(insight)
    assert restored.excluded_from_analysis is False
    assert evidence.is_valid is True
    assert evidence.invalidation_reasons_json == []
    assert evidence.invalidated_at is None
    assert insight.evidence_state is EvidenceState.VALID
    assert insight.revision_number == 2
    actions = list(
        db_session.scalars(
            select(InsightRevision.action)
            .where(InsightRevision.insight_id == insight.id)
            .order_by(InsightRevision.revision_number)
        )
    )
    assert actions == [
        InsightRevisionAction.EVIDENCE_INVALIDATED,
        InsightRevisionAction.EVIDENCE_REVALIDATED,
    ]


def test_other_invalidation_reason_is_preserved_on_reinclude(db_session: Session) -> None:
    graph = create_review_graph(db_session, insight_count=1, evidence_count=1)
    evidence = graph.evidence[0]
    evidence.invalidation_reasons_json = ["user_marked_invalid"]
    evidence.is_valid = False
    evidence.invalidated_at = NOW
    db_session.commit()

    set_message_analysis_exclusion(
        db_session,
        message_id=graph.messages[0].id,
        excluded=True,
        clock=fixed_clock,
    )
    set_message_analysis_exclusion(
        db_session,
        message_id=graph.messages[0].id,
        excluded=False,
        clock=fixed_clock,
    )
    db_session.refresh(evidence)
    assert evidence.is_valid is False
    assert evidence.invalidation_reasons_json == ["user_marked_invalid"]
    assert evidence.invalidated_at == NOW


@pytest.mark.parametrize("status", [InsightStatus.REJECTED, InsightStatus.SUPERSEDED])
def test_inactive_insight_updates_evidence_state_without_rescoring(
    db_session: Session,
    status: InsightStatus,
) -> None:
    graph = create_review_graph(
        db_session,
        insight_count=1,
        evidence_count=1,
        status=status,
    )
    insight = graph.insights[0]
    set_message_analysis_exclusion(
        db_session,
        message_id=graph.messages[0].id,
        excluded=True,
        clock=fixed_clock,
    )
    db_session.refresh(insight)
    assert insight.evidence_state is EvidenceState.INVALID
    assert insight.confidence_version == "unscored"
    assert insight.revision_number == 1


def test_confidence_failure_rolls_back_message_evidence_and_revision(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = create_review_graph(db_session, insight_count=1, evidence_count=1)
    message_id = graph.messages[0].id
    evidence_id = graph.evidence[0].id
    insight_id = graph.insights[0].id

    def fail_recalculation(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ApiError(
            "confidence_recalculation_failed",
            status_code=409,
            message="Synthetic confidence failure.",
        )

    monkeypatch.setattr(
        "echomind.services.evidence_validity_service.recalculate_for_review",
        fail_recalculation,
    )
    with pytest.raises(ApiError, match="Synthetic confidence failure"):
        set_message_analysis_exclusion(
            db_session,
            message_id=message_id,
            excluded=True,
            clock=fixed_clock,
        )

    evidence = db_session.get(Evidence, evidence_id)
    insight = db_session.get(Insight, insight_id)
    assert evidence is not None and evidence.is_valid is True
    assert evidence.invalidation_reasons_json == []
    assert insight is not None and insight.revision_number == 0
    assert (
        db_session.scalar(select(InsightRevision).where(InsightRevision.insight_id == insight_id))
        is None
    )

"""Stage 11 failure-injection checks for previously implicit transaction boundaries."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from tests.confidence.factories import create_confidence_graph
from tests.extraction.factories import ScriptedProvider, candidate, create_chat, session_factory_for
from tests.review.factories import create_review_graph

from echomind.confidence import ConfidenceCalculationRequest, calculate_confidence
from echomind.confidence import service as confidence_service
from echomind.extraction import service as extraction_service
from echomind.extraction.errors import ExtractionError, ExtractionErrorCode
from echomind.extraction.options import ExtractionRequest
from echomind.models import Evidence, Insight, InsightEvidence, InsightRevision
from echomind.models.enums import InsightStatus
from echomind.schemas.insight_review import ReviewActionRequest
from echomind.services import insight_review_service


def test_extraction_persistence_failure_leaves_no_partial_window(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    conversation, _, _ = create_chat(db_session)

    def fail_persistence(*args: object, **kwargs: object) -> None:
        raise ExtractionError(
            ExtractionErrorCode.PERSISTENCE_FAILED,
            message="Synthetic persistence failure.",
            request_id="00000000-0000-4000-8000-000000000011",
            recoverable=True,
        )

    monkeypatch.setattr(extraction_service, "persist_window", fail_persistence)
    report = extraction_service.extract_candidates(
        session_factory_for(db_session),
        ExtractionRequest(conversation_ids=[UUID(conversation.id)]),
        provider=ScriptedProvider([{"candidates": [candidate()]}]),
    )
    assert report.failed_window_count == 1
    assert report.errors[0].error_code == "persistence_failed"
    assert db_session.scalar(select(func.count()).select_from(Insight)) == 0
    assert db_session.scalar(select(func.count()).select_from(Evidence)) == 0
    assert db_session.scalar(select(func.count()).select_from(InsightEvidence)) == 0


def test_confidence_persistence_failure_retains_unscored_insight(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    insight, _ = create_confidence_graph(db_session)

    def fail_persistence(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("synthetic confidence persistence failure")

    monkeypatch.setattr(confidence_service, "persist_score", fail_persistence)
    report = calculate_confidence(
        session_factory_for(db_session),
        ConfidenceCalculationRequest(
            insight_ids=[UUID(insight.id)],
            as_of=datetime(2026, 7, 18, tzinfo=UTC),
            stop_on_error=False,
        ),
    )
    db_session.refresh(insight)
    assert report.failed_count == 1
    assert insight.confidence == 0.0
    assert insight.confidence_version == "unscored"
    assert insight.confidence_input_fingerprint is None


def test_revision_insert_failure_rolls_back_claimed_revision_and_status(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = create_review_graph(db_session, insight_count=1)
    insight = graph.insights[0]

    def fail_revision(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic revision write failure")

    monkeypatch.setattr(insight_review_service, "_add_revision", fail_revision)
    with pytest.raises(RuntimeError, match="synthetic revision write failure"):
        insight_review_service.confirm_insight(
            db_session,
            insight.id,
            ReviewActionRequest(expected_revision=0),
        )
    db_session.rollback()
    db_session.refresh(insight)
    assert insight.status is InsightStatus.PROPOSED
    assert insight.revision_number == 0
    assert db_session.scalar(select(func.count()).select_from(InsightRevision)) == 0

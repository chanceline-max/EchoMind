"""Review transitions, editing, supersession, and optimistic locking."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from echomind.api.errors import ApiError
from echomind.models.enums import EvidenceState, InsightRevisionAction, InsightStatus, InsightType
from echomind.models.insight_revision import InsightRevision
from echomind.schemas.insight_review import (
    BatchConfirmItem,
    BatchConfirmRequest,
    InsightEditRequest,
    RejectInsightRequest,
    RestoreInsightRequest,
    ReviewActionRequest,
    SupersedeInsightRequest,
)
from echomind.services.insight_review_service import (
    BATCH_CONFIRM_NOTE,
    batch_confirm_insights,
    confirm_insight,
    edit_insight,
    reject_insight,
    restore_insight,
    supersede_insight,
)
from tests.review.factories import create_review_graph

NOW = datetime(2026, 7, 20, 9, tzinfo=UTC)


def fixed_clock() -> datetime:
    return NOW


def test_edit_only_allows_review_fields_and_appends_snapshot(db_session: Session) -> None:
    insight = create_review_graph(db_session).insights[0]
    response = edit_insight(
        db_session,
        insight.id,
        InsightEditRequest(
            expected_revision=0,
            title="Revised synthetic title",
            statement="Revised synthetic statement.",
            review_note="Checked against the linked synthetic evidence.",
        ),
        clock=fixed_clock,
    )

    assert response.insight.revision_number == 1
    assert response.insight.title == "Revised synthetic title"
    assert response.revision.action is InsightRevisionAction.EDITED
    assert set(response.revision.changed_fields_json) == {
        "title",
        "statement",
        "review_note",
    }
    assert response.revision.snapshot_json["statement"] == "Revised synthetic statement."


def test_stale_revision_returns_conflict_before_status_validation(db_session: Session) -> None:
    insight = create_review_graph(db_session).insights[0]
    confirm_insight(
        db_session,
        insight.id,
        ReviewActionRequest(expected_revision=0),
        clock=fixed_clock,
    )

    with pytest.raises(ApiError) as caught:
        confirm_insight(
            db_session,
            insight.id,
            ReviewActionRequest(expected_revision=0),
            clock=fixed_clock,
        )
    assert caught.value.status_code == 409
    assert caught.value.payload.error_code == "insight_revision_conflict"
    assert caught.value.payload.details["current_revision"] == 1


def test_batch_confirm_records_an_independent_revision_for_each_eligible_insight(
    db_session: Session,
) -> None:
    first, second = create_review_graph(db_session).insights
    first.confidence = 0.5001
    second.confidence = 0.8
    db_session.commit()

    response = batch_confirm_insights(
        db_session,
        BatchConfirmRequest(
            items=[
                BatchConfirmItem(insight_id=first.id, expected_revision=0),
                BatchConfirmItem(insight_id=second.id, expected_revision=0),
            ]
        ),
        clock=fixed_clock,
    )

    assert response.confirmed_ids == [first.id, second.id]
    assert response.confirmed_count == 2
    revisions = list(
        db_session.scalars(select(InsightRevision).order_by(InsightRevision.insight_id))
    )
    assert len(revisions) == 2
    assert all(item.action is InsightRevisionAction.CONFIRMED for item in revisions)
    assert all(item.note == BATCH_CONFIRM_NOTE for item in revisions)


@pytest.mark.parametrize(
    ("confidence", "insight_type", "evidence_state"),
    [
        (0.5, InsightType.FACT, EvidenceState.VALID),
        (0.8, InsightType.INFERENCE, EvidenceState.VALID),
        (0.8, InsightType.HYPOTHESIS, EvidenceState.VALID),
        (0.8, InsightType.CONTRADICTION, EvidenceState.VALID),
        (0.8, InsightType.FACT, EvidenceState.PARTIAL),
    ],
)
def test_batch_confirm_rejects_manual_review_cases(
    db_session: Session,
    confidence: float,
    insight_type: InsightType,
    evidence_state: EvidenceState,
) -> None:
    first = create_review_graph(db_session, insight_count=1).insights[0]
    first.confidence = confidence
    first.insight_type = insight_type
    first.evidence_state = evidence_state
    db_session.commit()

    with pytest.raises(ApiError) as caught:
        batch_confirm_insights(
            db_session,
            BatchConfirmRequest(items=[BatchConfirmItem(insight_id=first.id, expected_revision=0)]),
            clock=fixed_clock,
        )
    assert caught.value.payload.error_code == "insight_not_batch_eligible"


def test_batch_confirm_is_atomic_when_a_later_item_is_not_eligible(
    db_session: Session,
) -> None:
    first, second = create_review_graph(db_session).insights
    first.confidence = 0.8
    second.confidence = 0.8
    second.insight_type = InsightType.INFERENCE
    db_session.commit()

    with pytest.raises(ApiError):
        batch_confirm_insights(
            db_session,
            BatchConfirmRequest(
                items=[
                    BatchConfirmItem(insight_id=first.id, expected_revision=0),
                    BatchConfirmItem(insight_id=second.id, expected_revision=0),
                ]
            ),
            clock=fixed_clock,
        )
    db_session.expire_all()
    assert first.status is InsightStatus.PROPOSED
    assert second.status is InsightStatus.PROPOSED
    assert db_session.scalar(select(InsightRevision).limit(1)) is None


def test_reject_requires_note_and_restore_recalculates(db_session: Session) -> None:
    insight = create_review_graph(db_session).insights[0]
    rejected = reject_insight(
        db_session,
        insight.id,
        RejectInsightRequest(expected_revision=0, note="Not currently supported."),
        clock=fixed_clock,
    )
    assert rejected.insight.status is InsightStatus.REJECTED
    assert rejected.insight.confidence_version == "unscored"

    restored = restore_insight(
        db_session,
        insight.id,
        RestoreInsightRequest(
            expected_revision=1,
            target_status=InsightStatus.PROPOSED,
            note="Evidence reviewed again.",
        ),
        clock=fixed_clock,
    )
    assert restored.insight.status is InsightStatus.PROPOSED
    assert restored.insight.confidence_version == "confidence-1.0"
    assert restored.revision.action is InsightRevisionAction.RESTORED_TO_PROPOSED


def test_type_edit_recalculates_but_statement_edit_does_not(db_session: Session) -> None:
    insight = create_review_graph(db_session).insights[0]
    statement = edit_insight(
        db_session,
        insight.id,
        InsightEditRequest(expected_revision=0, statement="Only wording changed."),
        clock=fixed_clock,
    )
    assert statement.insight.confidence_version == "unscored"

    typed = edit_insight(
        db_session,
        insight.id,
        InsightEditRequest(expected_revision=1, insight_type=InsightType.PREFERENCE),
        clock=fixed_clock,
    )
    assert typed.insight.confidence_version == "confidence-1.0"


def test_supersede_records_replacement_and_rejects_cycles(db_session: Session) -> None:
    first, second = create_review_graph(db_session).insights
    result = supersede_insight(
        db_session,
        first.id,
        SupersedeInsightRequest(
            expected_revision=0,
            replacement_insight_id=second.id,
            note="The second candidate is more precise.",
        ),
        clock=fixed_clock,
    )
    assert result.insight.status is InsightStatus.SUPERSEDED
    assert result.insight.superseded_by_insight_id == second.id

    with pytest.raises(ApiError) as caught:
        supersede_insight(
            db_session,
            second.id,
            SupersedeInsightRequest(
                expected_revision=0,
                replacement_insight_id=first.id,
            ),
            clock=fixed_clock,
        )
    assert caught.value.payload.error_code == "supersede_cycle_detected"


def test_supersede_rejects_self_inactive_targets_and_three_node_cycles(
    db_session: Session,
) -> None:
    first, second = create_review_graph(db_session).insights
    first_id, second_id = first.id, second.id
    with pytest.raises(ApiError) as self_error:
        supersede_insight(
            db_session,
            first_id,
            SupersedeInsightRequest(expected_revision=0, replacement_insight_id=first_id),
            clock=fixed_clock,
        )
    assert self_error.value.payload.error_code == "supersede_cycle_detected"
    db_session.rollback()

    second.status = InsightStatus.REJECTED
    db_session.commit()
    with pytest.raises(ApiError) as inactive:
        supersede_insight(
            db_session,
            first_id,
            SupersedeInsightRequest(expected_revision=0, replacement_insight_id=second_id),
            clock=fixed_clock,
        )
    assert inactive.value.payload.error_code == "invalid_supersede_target"
    db_session.rollback()

    second.status = InsightStatus.PROPOSED
    db_session.commit()
    third = create_review_graph(
        db_session,
        insight_count=1,
        conversation_suffix="2",
    ).insights[0]
    third_id = third.id
    supersede_insight(
        db_session,
        first_id,
        SupersedeInsightRequest(expected_revision=0, replacement_insight_id=second_id),
        clock=fixed_clock,
    )
    supersede_insight(
        db_session,
        second_id,
        SupersedeInsightRequest(expected_revision=0, replacement_insight_id=third_id),
        clock=fixed_clock,
    )
    with pytest.raises(ApiError) as cycle:
        supersede_insight(
            db_session,
            third_id,
            SupersedeInsightRequest(expected_revision=0, replacement_insight_id=first_id),
            clock=fixed_clock,
        )
    assert cycle.value.payload.error_code == "supersede_cycle_detected"


def test_revision_rows_are_append_only_at_orm_boundary(db_session: Session) -> None:
    insight = create_review_graph(db_session).insights[0]
    confirm_insight(
        db_session,
        insight.id,
        ReviewActionRequest(expected_revision=0),
        clock=fixed_clock,
    )
    revision = db_session.scalar(
        select(InsightRevision).where(InsightRevision.insight_id == insight.id)
    )
    assert revision is not None
    revision.note = "Attempted mutation"
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    revision = db_session.scalar(
        select(InsightRevision).where(InsightRevision.insight_id == insight.id)
    )
    assert revision is not None
    db_session.delete(revision)
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

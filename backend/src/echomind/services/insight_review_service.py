"""Transactional Insight review, optimistic concurrency, and append-only history."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from echomind.api.errors import ApiError
from echomind.confidence import ConfidenceError, recalculate_confidence_in_session
from echomind.db.types import utc_now
from echomind.models import Insight
from echomind.models.enums import (
    EvidenceInvalidationReason,
    InsightRevisionAction,
    InsightStatus,
    RevisionActorType,
)
from echomind.models.insight_revision import InsightRevision
from echomind.repositories import insight_review_repository as repository
from echomind.schemas.insight_review import (
    AllowedAction,
    EvidenceDetail,
    InsightDetail,
    InsightEditRequest,
    InsightPage,
    InsightRevisionPage,
    InsightRevisionRead,
    InsightSummary,
    RejectInsightRequest,
    RestoreInsightRequest,
    ReviewActionRequest,
    ReviewMutationResponse,
    SupersedeInsightRequest,
)

Clock = Callable[[], datetime]
STATEMENT_SUMMARY_LIMIT = 240


def _now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("review clock must return a timezone-aware datetime")
    return value.astimezone(UTC)


def _safe_time(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def review_snapshot(insight: Insight) -> dict[str, Any]:
    return {
        "title": insight.title,
        "statement": insight.statement,
        "category": insight.category,
        "insight_type": insight.insight_type.value,
        "status": insight.status.value,
        "confidence": insight.confidence,
        "confidence_version": insight.confidence_version,
        "evidence_state": insight.evidence_state.value,
        "valid_from": _safe_time(insight.valid_from),
        "valid_to": _safe_time(insight.valid_to),
        "review_note": insight.review_note,
        "superseded_by_insight_id": insight.superseded_by_insight_id,
    }


def _changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        field: {"old": before[field], "new": after[field]}
        for field in before
        if before[field] != after[field]
    }


def _revision_read(revision: InsightRevision) -> InsightRevisionRead:
    return InsightRevisionRead(
        id=revision.id,
        insight_id=revision.insight_id,
        revision_number=revision.revision_number,
        action=revision.action,
        actor_type=revision.actor_type,
        created_at=revision.created_at,
        expected_previous_revision=revision.expected_previous_revision,
        changed_fields_json=dict(revision.changed_fields_json),
        snapshot_json=dict(revision.snapshot_json),
        note=revision.note,
    )


def _summary(insight: Insight, counts: repository.InsightCounts) -> InsightSummary:
    statement = insight.statement
    statement_summary = (
        statement
        if len(statement) <= STATEMENT_SUMMARY_LIMIT
        else f"{statement[: STATEMENT_SUMMARY_LIMIT - 1]}…"
    )
    return InsightSummary(
        id=insight.id,
        title=insight.title,
        statement_summary=statement_summary,
        category=insight.category,
        insight_type=insight.insight_type,
        status=insight.status,
        confidence=insight.confidence,
        confidence_version=insight.confidence_version,
        model_confidence=insight.model_confidence,
        evidence_state=insight.evidence_state,
        evidence_count=counts.evidence_count,
        valid_evidence_count=counts.valid_evidence_count,
        contradicting_evidence_count=counts.contradicting_evidence_count,
        valid_from=insight.valid_from,
        valid_to=insight.valid_to,
        revision_number=insight.revision_number,
        reviewed_at=insight.reviewed_at,
        superseded_by_insight_id=insight.superseded_by_insight_id,
        created_at=insight.created_at,
        updated_at=insight.updated_at,
    )


def _allowed_actions(status: InsightStatus) -> list[AllowedAction]:
    if status is InsightStatus.PROPOSED:
        return ["edit", "confirm", "reject", "supersede"]
    if status is InsightStatus.CONFIRMED:
        return ["edit", "reject", "supersede"]
    return ["edit", "confirm", "restore_to_proposed", "restore_to_confirmed"]


def _detail(session: Session, insight: Insight) -> InsightDetail:
    counts = repository.insight_counts(session, insight.id)
    summary = _summary(insight, counts)
    evidence = [
        EvidenceDetail(
            evidence_id=item.id,
            evidence_type=item.evidence_type,
            stance=item.stance.value,
            relevance_score=item.relevance_score,
            is_valid=item.is_valid,
            invalidation_reasons=[
                EvidenceInvalidationReason(reason) for reason in item.invalidation_reasons_json
            ],
            invalidated_at=item.invalidated_at,
            excerpt=item.excerpt,
            message_id=message.id,
            conversation_id=message.conversation_id,
            message_timestamp=message.timestamp,
            sender_role="PROFILE_OWNER" if is_owner else "OTHER",
            message_excluded_from_analysis=message.excluded_from_analysis,
            message_link=(f"/conversations/{message.conversation_id}?message={message.id}"),
        )
        for item, message, is_owner in repository.evidence_rows(session, insight.id)
    ]
    return InsightDetail(
        **summary.model_dump(),
        statement=insight.statement,
        reasoning_basis=insight.reasoning_basis,
        alternative_explanations=list(insight.alternative_explanations),
        explicit_self_report=insight.explicit_self_report,
        extraction_version=insight.extraction_version,
        provider_name=insight.provider_name,
        confidence_explanation=insight.confidence_explanation,
        confidence_factors=(
            dict(insight.confidence_factors_json)
            if insight.confidence_factors_json is not None
            else None
        ),
        review_note=insight.review_note,
        evidence=evidence,
        allowed_actions=_allowed_actions(insight.status),
    )


def list_insights(session: Session, **filters: Any) -> InsightPage:
    rows, total = repository.list_insights(session, **filters)
    return InsightPage(
        items=[_summary(insight, counts) for insight, counts in rows],
        total=total,
        limit=int(filters["limit"]),
        offset=int(filters["offset"]),
    )


def get_insight_detail(session: Session, insight_id: str) -> InsightDetail:
    insight = repository.get_insight(session, insight_id)
    if insight is None:
        raise ApiError(
            "insight_not_found",
            status_code=404,
            message="The requested Insight does not exist.",
        )
    return _detail(session, insight)


def get_revisions(
    session: Session,
    insight_id: str,
    *,
    limit: int,
    offset: int,
) -> InsightRevisionPage:
    if repository.get_insight(session, insight_id) is None:
        raise ApiError(
            "insight_not_found",
            status_code=404,
            message="The requested Insight does not exist.",
        )
    items, total = repository.list_revisions(session, insight_id, limit=limit, offset=offset)
    return InsightRevisionPage(
        items=[_revision_read(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def _claim_revision(
    session: Session,
    insight: Insight,
    *,
    expected_revision: int,
    changed_at: datetime,
) -> int:
    result: CursorResult[Any] = session.connection().execute(
        update(Insight)
        .where(
            Insight.id == insight.id,
            Insight.revision_number == expected_revision,
        )
        .values(
            revision_number=expected_revision + 1,
            updated_at=changed_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        current = session.get(Insight, insight.id, populate_existing=True)
        current_revision = current.revision_number if current is not None else -1
        raise ApiError(
            "insight_revision_conflict",
            status_code=409,
            message="The Insight was updated by another operation.",
            recoverable=True,
            details={
                "expected_revision": expected_revision,
                "current_revision": current_revision,
                "insight_id": insight.id,
            },
        )
    insight.revision_number = expected_revision + 1
    insight.updated_at = changed_at
    return expected_revision + 1


def _ensure_expected_revision(insight: Insight, expected_revision: int) -> None:
    if insight.revision_number == expected_revision:
        return
    raise ApiError(
        "insight_revision_conflict",
        status_code=409,
        message="The Insight was updated by another operation.",
        recoverable=True,
        details={
            "expected_revision": expected_revision,
            "current_revision": insight.revision_number,
            "insight_id": insight.id,
        },
    )


def _add_revision(
    session: Session,
    insight: Insight,
    *,
    action: InsightRevisionAction,
    actor: RevisionActorType,
    expected_previous_revision: int,
    before: dict[str, Any],
    note: str | None,
    created_at: datetime,
) -> InsightRevision:
    after = review_snapshot(insight)
    revision = InsightRevision(
        insight_id=insight.id,
        revision_number=insight.revision_number,
        action=action,
        actor_type=actor,
        created_at=created_at,
        expected_previous_revision=expected_previous_revision,
        changed_fields_json=_changes(before, after),
        snapshot_json=after,
        note=note,
    )
    session.add(revision)
    session.flush()
    return revision


def _recalculate(session: Session, insight: Insight, now: datetime) -> None:
    try:
        recalculate_confidence_in_session(
            session,
            insight.id,
            as_of=now,
            calculated_at=now,
            request_id=str(uuid4()),
        )
        session.refresh(insight)
    except ConfidenceError:
        raise ApiError(
            "confidence_recalculation_failed",
            status_code=409,
            message="The Insight confidence could not be recalculated safely.",
            recoverable=True,
            details={"insight_id": insight.id},
        ) from None


def _mutation_response(
    session: Session,
    insight: Insight,
    revision: InsightRevision,
) -> ReviewMutationResponse:
    return ReviewMutationResponse(
        insight=_detail(session, insight),
        revision=_revision_read(revision),
    )


def edit_insight(
    session: Session,
    insight_id: str,
    payload: InsightEditRequest,
    *,
    clock: Clock = utc_now,
) -> ReviewMutationResponse:
    now = _now(clock)
    with session.begin():
        insight = repository.get_insight(session, insight_id)
        if insight is None:
            raise ApiError(
                "insight_not_found",
                status_code=404,
                message="The requested Insight does not exist.",
            )
        _ensure_expected_revision(insight, payload.expected_revision)
        before = review_snapshot(insight)
        _claim_revision(
            session,
            insight,
            expected_revision=payload.expected_revision,
            changed_at=now,
        )
        for field in payload.model_fields_set - {"expected_revision"}:
            setattr(insight, field, getattr(payload, field))
        if insight.valid_from and insight.valid_to and insight.valid_to < insight.valid_from:
            raise ApiError(
                "insight_edit_invalid",
                status_code=422,
                message="The Insight valid time range is not valid.",
            )
        insight.reviewed_at = now
        session.flush()
        confidence_inputs = {"insight_type", "valid_from", "valid_to"}
        changed_input = any(field in payload.model_fields_set for field in confidence_inputs)
        if changed_input:
            _recalculate(session, insight, now)
        after = review_snapshot(insight)
        if not _changes(before, after):
            raise ApiError(
                "insight_edit_invalid",
                status_code=422,
                message="The edit does not change the Insight.",
            )
        revision = _add_revision(
            session,
            insight,
            action=InsightRevisionAction.EDITED,
            actor=RevisionActorType.LOCAL_USER,
            expected_previous_revision=payload.expected_revision,
            before=before,
            note=insight.review_note,
            created_at=now,
        )
        return _mutation_response(session, insight, revision)


def _transition(
    session: Session,
    insight_id: str,
    *,
    expected_revision: int,
    target_status: InsightStatus,
    allowed_from: set[InsightStatus],
    action: InsightRevisionAction,
    restored_action: InsightRevisionAction | None = None,
    note: str | None,
    clock: Clock,
    recalculate: bool = False,
) -> ReviewMutationResponse:
    now = _now(clock)
    with session.begin():
        insight = repository.get_insight(session, insight_id)
        if insight is None:
            raise ApiError(
                "insight_not_found",
                status_code=404,
                message="The requested Insight does not exist.",
            )
        _ensure_expected_revision(insight, expected_revision)
        previous_status = insight.status
        if insight.status not in allowed_from:
            raise ApiError(
                "invalid_status_transition",
                status_code=409,
                message="The requested Insight status transition is not allowed.",
                details={
                    "current_status": insight.status.value,
                    "target_status": target_status.value,
                },
            )
        before = review_snapshot(insight)
        _claim_revision(session, insight, expected_revision=expected_revision, changed_at=now)
        insight.status = target_status
        insight.superseded_by_insight_id = None
        insight.review_note = note
        insight.reviewed_at = now
        session.flush()
        if recalculate:
            _recalculate(session, insight, now)
        revision = _add_revision(
            session,
            insight,
            action=(
                restored_action
                if restored_action is not None
                and previous_status in {InsightStatus.REJECTED, InsightStatus.SUPERSEDED}
                else action
            ),
            actor=RevisionActorType.LOCAL_USER,
            expected_previous_revision=expected_revision,
            before=before,
            note=note,
            created_at=now,
        )
        return _mutation_response(session, insight, revision)


def confirm_insight(
    session: Session,
    insight_id: str,
    payload: ReviewActionRequest,
    *,
    clock: Clock = utc_now,
) -> ReviewMutationResponse:
    return _transition(
        session,
        insight_id,
        expected_revision=payload.expected_revision,
        target_status=InsightStatus.CONFIRMED,
        allowed_from={InsightStatus.PROPOSED, InsightStatus.REJECTED, InsightStatus.SUPERSEDED},
        action=InsightRevisionAction.CONFIRMED,
        restored_action=InsightRevisionAction.RESTORED_TO_CONFIRMED,
        note=payload.note,
        clock=clock,
    )


def reject_insight(
    session: Session,
    insight_id: str,
    payload: RejectInsightRequest,
    *,
    clock: Clock = utc_now,
) -> ReviewMutationResponse:
    return _transition(
        session,
        insight_id,
        expected_revision=payload.expected_revision,
        target_status=InsightStatus.REJECTED,
        allowed_from={InsightStatus.PROPOSED, InsightStatus.CONFIRMED},
        action=InsightRevisionAction.REJECTED,
        note=payload.note,
        clock=clock,
    )


def restore_insight(
    session: Session,
    insight_id: str,
    payload: RestoreInsightRequest,
    *,
    clock: Clock = utc_now,
) -> ReviewMutationResponse:
    target = InsightStatus(payload.target_status)
    return _transition(
        session,
        insight_id,
        expected_revision=payload.expected_revision,
        target_status=target,
        allowed_from={InsightStatus.REJECTED, InsightStatus.SUPERSEDED},
        action=(
            InsightRevisionAction.RESTORED_TO_PROPOSED
            if target is InsightStatus.PROPOSED
            else InsightRevisionAction.RESTORED_TO_CONFIRMED
        ),
        note=payload.note,
        clock=clock,
        recalculate=True,
    )


def _assert_no_supersede_cycle(
    session: Session,
    current_id: str,
    replacement_id: str,
) -> Insight:
    seen = {current_id}
    cursor: str | None = replacement_id
    replacement: Insight | None = None
    while cursor is not None:
        if cursor in seen:
            raise ApiError(
                "supersede_cycle_detected",
                status_code=409,
                message="The supersede relationship would create a cycle.",
                details={"insight_id": current_id, "replacement_insight_id": replacement_id},
            )
        seen.add(cursor)
        item = repository.get_insight(session, cursor)
        if item is None:
            if cursor == replacement_id:
                raise ApiError(
                    "replacement_insight_not_found",
                    status_code=404,
                    message="The replacement Insight does not exist.",
                )
            break
        if replacement is None:
            replacement = item
        cursor = item.superseded_by_insight_id
    if replacement is None:
        raise ApiError(
            "replacement_insight_not_found",
            status_code=404,
            message="The replacement Insight does not exist.",
        )
    if replacement.status in {InsightStatus.REJECTED, InsightStatus.SUPERSEDED}:
        raise ApiError(
            "invalid_supersede_target",
            status_code=409,
            message="The replacement Insight is not an active candidate.",
            details={"replacement_status": replacement.status.value},
        )
    return replacement


def supersede_insight(
    session: Session,
    insight_id: str,
    payload: SupersedeInsightRequest,
    *,
    clock: Clock = utc_now,
) -> ReviewMutationResponse:
    now = _now(clock)
    with session.begin():
        insight = repository.get_insight(session, insight_id)
        if insight is None:
            raise ApiError(
                "insight_not_found",
                status_code=404,
                message="The requested Insight does not exist.",
            )
        _ensure_expected_revision(insight, payload.expected_revision)
        if insight.status not in {InsightStatus.PROPOSED, InsightStatus.CONFIRMED}:
            raise ApiError(
                "invalid_status_transition",
                status_code=409,
                message="Only proposed or confirmed Insights can be superseded.",
            )
        _assert_no_supersede_cycle(session, insight.id, payload.replacement_insight_id)
        before = review_snapshot(insight)
        _claim_revision(
            session,
            insight,
            expected_revision=payload.expected_revision,
            changed_at=now,
        )
        insight.status = InsightStatus.SUPERSEDED
        insight.superseded_by_insight_id = payload.replacement_insight_id
        insight.review_note = payload.note
        insight.reviewed_at = now
        session.flush()
        revision = _add_revision(
            session,
            insight,
            action=InsightRevisionAction.SUPERSEDED,
            actor=RevisionActorType.LOCAL_USER,
            expected_previous_revision=payload.expected_revision,
            before=before,
            note=payload.note,
            created_at=now,
        )
        return _mutation_response(session, insight, revision)


def add_system_revision(
    session: Session,
    insight: Insight,
    *,
    action: InsightRevisionAction,
    before: dict[str, Any],
    changed_at: datetime,
) -> InsightRevision:
    previous = insight.revision_number
    _claim_revision(session, insight, expected_revision=previous, changed_at=changed_at)
    return _add_revision(
        session,
        insight,
        action=action,
        actor=RevisionActorType.SYSTEM,
        expected_previous_revision=previous,
        before=before,
        note=None,
        created_at=changed_at,
    )


def recalculate_for_review(session: Session, insight: Insight, changed_at: datetime) -> None:
    _recalculate(session, insight, changed_at)

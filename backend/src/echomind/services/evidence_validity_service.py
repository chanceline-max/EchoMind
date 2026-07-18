"""Propagate final Message exclusion to Evidence and related Insights atomically."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from echomind.api.errors import ApiError
from echomind.db.types import utc_now
from echomind.models import Insight, Message
from echomind.models.enums import (
    EvidenceInvalidationReason,
    EvidenceState,
    InsightRevisionAction,
    InsightStatus,
)
from echomind.repositories import insight_review_repository as repository
from echomind.schemas.messages import MessageSummary
from echomind.services.conversation_service import message_summary
from echomind.services.insight_review_service import (
    add_system_revision,
    recalculate_for_review,
    review_snapshot,
)

Clock = Callable[[], datetime]
USER_EXCLUDED = "user_excluded"
SOURCE_MESSAGE_EXCLUDED = EvidenceInvalidationReason.SOURCE_MESSAGE_EXCLUDED.value


def _now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evidence validity clock must return an aware datetime")
    return value.astimezone(UTC)


def _derived_state(session: Session, insight_id: str) -> EvidenceState:
    counts = repository.insight_counts(session, insight_id)
    if counts.valid_evidence_count == 0:
        return EvidenceState.INVALID
    if counts.valid_evidence_count == counts.evidence_count:
        return EvidenceState.VALID
    return EvidenceState.PARTIAL


def set_message_analysis_exclusion(
    session: Session,
    *,
    message_id: str,
    excluded: bool,
    clock: Clock = utc_now,
) -> MessageSummary:
    now = _now(clock)
    with session.begin():
        message = session.get(Message, message_id)
        if message is None:
            raise ApiError(
                "resource_not_found",
                status_code=404,
                message="The requested message does not exist.",
            )
        reasons = list(dict.fromkeys(message.exclusion_reasons_json))
        if excluded and USER_EXCLUDED not in reasons:
            reasons.append(USER_EXCLUDED)
        if not excluded:
            reasons = [item for item in reasons if item != USER_EXCLUDED]
        message.exclusion_reasons_json = reasons
        message.exclusion_reason = reasons[0] if reasons else None
        message.excluded_from_analysis = bool(reasons)

        linked_evidence = repository.linked_evidence_for_message(session, message.id)
        changed_evidence_ids: set[str] = set()
        for evidence in linked_evidence:
            evidence_reasons = list(dict.fromkeys(evidence.invalidation_reasons_json))
            before_reasons = list(evidence_reasons)
            if message.excluded_from_analysis:
                if SOURCE_MESSAGE_EXCLUDED not in evidence_reasons:
                    evidence_reasons.append(SOURCE_MESSAGE_EXCLUDED)
            else:
                evidence_reasons = [
                    item for item in evidence_reasons if item != SOURCE_MESSAGE_EXCLUDED
                ]
            if evidence_reasons == before_reasons:
                continue
            was_valid = evidence.is_valid
            evidence.invalidation_reasons_json = evidence_reasons
            evidence.invalidation_reason = evidence_reasons[0] if evidence_reasons else None
            evidence.is_valid = not evidence_reasons
            if was_valid and not evidence.is_valid:
                evidence.invalidated_at = now
            elif evidence.is_valid:
                evidence.invalidated_at = None
            changed_evidence_ids.add(evidence.id)

        session.flush()
        if changed_evidence_ids:
            action = (
                InsightRevisionAction.EVIDENCE_INVALIDATED
                if message.excluded_from_analysis
                else InsightRevisionAction.EVIDENCE_REVALIDATED
            )
            for insight_id in repository.related_insight_ids_for_message(session, message.id):
                insight = session.get(Insight, insight_id)
                if insight is None:
                    raise ApiError(
                        "evidence_propagation_failed",
                        status_code=409,
                        message="An affected Insight could not be updated safely.",
                    )
                before = review_snapshot(insight)
                if insight.status in {InsightStatus.PROPOSED, InsightStatus.CONFIRMED}:
                    recalculate_for_review(session, insight, now)
                else:
                    insight.evidence_state = _derived_state(session, insight.id)
                    session.flush()
                add_system_revision(
                    session,
                    insight,
                    action=action,
                    before=before,
                    changed_at=now,
                )

        session.flush()
        row = repository.get_message_with_sender(session, message.id)
        if row is None:
            raise ApiError(
                "resource_not_found",
                status_code=404,
                message="The requested message does not exist.",
            )
        return message_summary(*row)

"""Concrete, stage-nine queries for Insight review and Evidence traceability."""

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, and_, case, exists, func, select
from sqlalchemy.orm import Session

from echomind.models import Conversation, Evidence, Insight, InsightEvidence, Message, Participant
from echomind.models.enums import EvidenceStance, EvidenceState, InsightStatus, InsightType
from echomind.models.insight_revision import InsightRevision


@dataclass(frozen=True)
class InsightCounts:
    evidence_count: int
    valid_evidence_count: int
    contradicting_evidence_count: int


def _evidence_stats() -> Select[tuple[str, int, int, int]]:
    return (
        select(
            InsightEvidence.insight_id.label("insight_id"),
            func.count(Evidence.id).label("evidence_count"),
            func.sum(case((Evidence.is_valid.is_(True), 1), else_=0)).label("valid_count"),
            func.sum(
                case(
                    (
                        and_(
                            Evidence.is_valid.is_(True),
                            Evidence.stance == EvidenceStance.CONTRADICTS,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("contradicting_count"),
        )
        .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
        .group_by(InsightEvidence.insight_id)
    )


def _filters(
    *,
    status: InsightStatus | None,
    insight_type: InsightType | None,
    category: str | None,
    evidence_state: EvidenceState | None,
    min_confidence: float | None,
    max_confidence: float | None,
    conversation_id: str | None,
    source_file_id: str | None,
    has_contradicting_evidence: bool | None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if status is not None:
        filters.append(Insight.status == status)
    if insight_type is not None:
        filters.append(Insight.insight_type == insight_type)
    if category is not None:
        filters.append(Insight.category == category)
    if evidence_state is not None:
        filters.append(Insight.evidence_state == evidence_state)
    if min_confidence is not None:
        filters.append(Insight.confidence >= min_confidence)
    if max_confidence is not None:
        filters.append(Insight.confidence <= max_confidence)
    if conversation_id is not None:
        filters.append(
            exists(
                select(1)
                .select_from(InsightEvidence)
                .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
                .join(Message, Message.id == Evidence.message_id)
                .where(
                    InsightEvidence.insight_id == Insight.id,
                    Message.conversation_id == conversation_id,
                )
            )
        )
    if source_file_id is not None:
        filters.append(
            exists(
                select(1)
                .select_from(InsightEvidence)
                .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
                .join(Message, Message.id == Evidence.message_id)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(
                    InsightEvidence.insight_id == Insight.id,
                    Conversation.source_file_id == source_file_id,
                )
            )
        )
    if has_contradicting_evidence is not None:
        has_contradiction = exists(
            select(1)
            .select_from(InsightEvidence)
            .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
            .where(
                InsightEvidence.insight_id == Insight.id,
                Evidence.is_valid.is_(True),
                Evidence.stance == EvidenceStance.CONTRADICTS,
            )
        )
        filters.append(has_contradiction if has_contradicting_evidence else ~has_contradiction)
    return filters


def list_insights(
    session: Session,
    *,
    status: InsightStatus | None,
    insight_type: InsightType | None,
    category: str | None,
    evidence_state: EvidenceState | None,
    min_confidence: float | None,
    max_confidence: float | None,
    conversation_id: str | None,
    source_file_id: str | None,
    has_contradicting_evidence: bool | None,
    limit: int,
    offset: int,
    sort: str,
) -> tuple[list[tuple[Insight, InsightCounts]], int]:
    filters = _filters(
        status=status,
        insight_type=insight_type,
        category=category,
        evidence_state=evidence_state,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        conversation_id=conversation_id,
        source_file_id=source_file_id,
        has_contradicting_evidence=has_contradicting_evidence,
    )
    total = session.scalar(select(func.count()).select_from(Insight).where(*filters)) or 0
    stats = _evidence_stats().subquery()
    order = cast(
        ColumnElement[Any],
        {
            "created_at_desc": Insight.created_at.desc(),
            "updated_at_desc": Insight.updated_at.desc(),
            "confidence_desc": Insight.confidence.desc(),
            "confidence_asc": Insight.confidence.asc(),
        }[sort],
    )
    rows = session.execute(
        select(
            Insight,
            func.coalesce(stats.c.evidence_count, 0),
            func.coalesce(stats.c.valid_count, 0),
            func.coalesce(stats.c.contradicting_count, 0),
        )
        .outerjoin(stats, stats.c.insight_id == Insight.id)
        .where(*filters)
        .order_by(order, Insight.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        (
            insight,
            InsightCounts(
                evidence_count=int(evidence_count),
                valid_evidence_count=int(valid_count),
                contradicting_evidence_count=int(contradicting_count),
            ),
        )
        for insight, evidence_count, valid_count, contradicting_count in rows
    ], int(total)


def get_insight(session: Session, insight_id: str) -> Insight | None:
    return session.get(Insight, insight_id)


def insight_counts(session: Session, insight_id: str) -> InsightCounts:
    stats = _evidence_stats().subquery()
    row = session.execute(
        select(
            func.coalesce(stats.c.evidence_count, 0),
            func.coalesce(stats.c.valid_count, 0),
            func.coalesce(stats.c.contradicting_count, 0),
        ).where(stats.c.insight_id == insight_id)
    ).one_or_none()
    return InsightCounts(0, 0, 0) if row is None else InsightCounts(*(int(item) for item in row))


def evidence_rows(session: Session, insight_id: str) -> list[tuple[Evidence, Message, bool]]:
    return [
        (evidence, message, bool(is_profile_owner))
        for evidence, message, is_profile_owner in session.execute(
            select(Evidence, Message, Participant.is_profile_owner)
            .select_from(InsightEvidence)
            .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
            .join(Message, Message.id == Evidence.message_id)
            .join(Participant, Participant.id == Message.sender_id)
            .where(InsightEvidence.insight_id == insight_id)
            .order_by(Message.timestamp.asc(), Message.source_order.asc(), Evidence.id.asc())
        )
    ]


def list_revisions(
    session: Session,
    insight_id: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[InsightRevision], int]:
    filters = [InsightRevision.insight_id == insight_id]
    total = session.scalar(select(func.count()).select_from(InsightRevision).where(*filters)) or 0
    items = list(
        session.scalars(
            select(InsightRevision)
            .where(*filters)
            .order_by(InsightRevision.revision_number.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, int(total)


def related_insight_ids_for_message(session: Session, message_id: str) -> list[str]:
    return list(
        session.scalars(
            select(InsightEvidence.insight_id)
            .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
            .where(Evidence.message_id == message_id)
            .distinct()
            .order_by(InsightEvidence.insight_id.asc())
        )
    )


def linked_evidence_for_message(session: Session, message_id: str) -> list[Evidence]:
    return list(
        session.scalars(
            select(Evidence).where(Evidence.message_id == message_id).order_by(Evidence.id)
        )
    )


def get_message_with_sender(session: Session, message_id: str) -> tuple[Message, str] | None:
    row = session.execute(
        select(Message, Participant.canonical_name)
        .join(Participant, Participant.id == Message.sender_id)
        .where(Message.id == message_id)
    ).one_or_none()
    return None if row is None else (row[0], row[1])


def message_location(
    session: Session,
    message_id: str,
    *,
    page_size: int = 20,
) -> tuple[str, int, int] | None:
    message = session.get(Message, message_id)
    if message is None:
        return None
    earlier = (
        session.scalar(
            select(func.count())
            .select_from(Message)
            .where(
                Message.conversation_id == message.conversation_id,
                (Message.source_order < message.source_order)
                | and_(Message.source_order == message.source_order, Message.id < message.id),
            )
        )
        or 0
    )
    index = int(earlier)
    return message.conversation_id, index, (index // page_size) * page_size


def supersede_target(session: Session, insight_id: str) -> str | None:
    return session.scalar(select(Insight.superseded_by_insight_id).where(Insight.id == insight_id))

"""Focused database access for Profile source reads and immutable snapshots."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from echomind.models import Conversation, Evidence, Insight, InsightEvidence, Message, Participant
from echomind.models.enums import EvidenceState, InsightStatus, InsightType
from echomind.models.profile_snapshot import ProfileSnapshot
from echomind.profiling.errors import ProfileError
from echomind.profiling.options import ProfileGenerationRequest


@dataclass(frozen=True)
class ProfileEvidenceSource:
    evidence_id: str
    message_id: str
    conversation_id: str
    source_file_id: str
    evidence_type: str
    role: Literal["supports", "contradicts", "context"]
    relevance_score: float
    is_valid: bool
    invalidation_reasons: tuple[str, ...]
    invalidated_at: datetime | None
    evidence_fingerprint: str | None
    message_timestamp: datetime | None
    sender_role: Literal["PROFILE_OWNER", "OTHER"]
    excerpt: str


@dataclass(frozen=True)
class ProfileInsightSource:
    id: str
    revision_number: int
    status: InsightStatus
    insight_type: InsightType
    category: str
    title: str
    statement: str
    confidence: float
    confidence_version: str
    confidence_input_fingerprint: str | None
    confidence_explanation: str | None
    confidence_factors: dict[str, object] | None
    evidence_state: EvidenceState
    explicit_self_report: bool
    valid_from: datetime | None
    valid_to: datetime | None
    updated_at: datetime
    reasoning_basis: str | None
    alternative_explanations: tuple[str, ...]
    evidence: tuple[ProfileEvidenceSource, ...]


def load_profile_sources(
    session: Session,
    request: ProfileGenerationRequest,
    *,
    require_confirmed: bool = True,
) -> list[ProfileInsightSource]:
    if request.scope == "all_confirmed":
        insights = list(
            session.scalars(
                select(Insight)
                .where(Insight.status == InsightStatus.CONFIRMED)
                .order_by(Insight.id)
            )
        )
    else:
        requested_ids = [str(value) for value in request.selected_insight_ids]
        found = list(session.scalars(select(Insight).where(Insight.id.in_(requested_ids))))
        by_id = {item.id: item for item in found}
        missing = [item for item in requested_ids if item not in by_id]
        if missing:
            raise ProfileError(
                "selected_insight_not_found",
                "A selected Insight does not exist.",
                status_code=404,
                details={"count": len(missing)},
            )
        insights = [by_id[item] for item in requested_ids]
        if require_confirmed:
            not_confirmed = [item for item in insights if item.status != InsightStatus.CONFIRMED]
            if not_confirmed:
                raise ProfileError(
                    "selected_insight_not_confirmed",
                    "Every selected Insight must be confirmed.",
                    details={"count": len(not_confirmed)},
                )

    if not insights:
        raise ProfileError("no_confirmed_insights", "No confirmed Insights are available.")

    insight_ids = [item.id for item in insights]
    rows = session.execute(
        select(
            InsightEvidence.insight_id,
            Evidence,
            Message.id,
            Message.conversation_id,
            Message.timestamp,
            Participant.is_profile_owner,
            Conversation.source_file_id,
        )
        .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
        .join(Message, Message.id == Evidence.message_id)
        .join(Participant, Participant.id == Message.sender_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(InsightEvidence.insight_id.in_(insight_ids))
        .order_by(InsightEvidence.insight_id, Evidence.id)
    ).all()
    evidence_by_insight: dict[str, list[ProfileEvidenceSource]] = {item: [] for item in insight_ids}
    for (
        insight_id,
        evidence,
        message_id,
        conversation_id,
        message_timestamp,
        owner,
        source_file_id,
    ) in rows:
        evidence_by_insight[insight_id].append(
            ProfileEvidenceSource(
                evidence_id=evidence.id,
                message_id=message_id,
                conversation_id=conversation_id,
                source_file_id=source_file_id,
                evidence_type=evidence.evidence_type,
                role=evidence.stance.value,
                relevance_score=evidence.relevance_score,
                is_valid=evidence.is_valid,
                invalidation_reasons=tuple(sorted(evidence.invalidation_reasons_json)),
                invalidated_at=evidence.invalidated_at,
                evidence_fingerprint=evidence.evidence_fingerprint,
                message_timestamp=message_timestamp,
                sender_role="PROFILE_OWNER" if owner else "OTHER",
                excerpt=evidence.excerpt,
            )
        )
    return [
        ProfileInsightSource(
            id=item.id,
            revision_number=item.revision_number,
            status=item.status,
            insight_type=item.insight_type,
            category=item.category,
            title=item.title,
            statement=item.statement,
            confidence=item.confidence,
            confidence_version=item.confidence_version,
            confidence_input_fingerprint=item.confidence_input_fingerprint,
            confidence_explanation=item.confidence_explanation,
            confidence_factors=item.confidence_factors_json,
            evidence_state=item.evidence_state,
            explicit_self_report=item.explicit_self_report,
            valid_from=item.valid_from,
            valid_to=item.valid_to,
            updated_at=item.updated_at,
            reasoning_basis=item.reasoning_basis,
            alternative_explanations=tuple(item.alternative_explanations),
            evidence=tuple(evidence_by_insight[item.id]),
        )
        for item in insights
    ]


def find_by_generation_fingerprint(
    session: Session, generation_fingerprint: str
) -> ProfileSnapshot | None:
    return session.scalar(
        select(ProfileSnapshot).where(
            ProfileSnapshot.generation_fingerprint == generation_fingerprint
        )
    )


def add_snapshot(session: Session, snapshot: ProfileSnapshot) -> tuple[ProfileSnapshot, bool]:
    existing = find_by_generation_fingerprint(session, snapshot.generation_fingerprint or "")
    if existing is not None:
        return existing, False
    session.add(snapshot)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = find_by_generation_fingerprint(session, snapshot.generation_fingerprint or "")
        if existing is None:
            raise
        return existing, False
    session.refresh(snapshot)
    return snapshot, True


def get_snapshot(session: Session, profile_id: str) -> ProfileSnapshot | None:
    return session.get(ProfileSnapshot, profile_id)


def list_snapshots(
    session: Session, *, limit: int, offset: int, profile_version: str | None
) -> tuple[list[ProfileSnapshot], int]:
    filters = (
        [] if profile_version is None else [ProfileSnapshot.profile_version == profile_version]
    )
    total = session.scalar(select(func.count()).select_from(ProfileSnapshot).where(*filters)) or 0
    items = list(
        session.scalars(
            select(ProfileSnapshot)
            .where(*filters)
            .order_by(ProfileSnapshot.generated_at.desc(), ProfileSnapshot.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total

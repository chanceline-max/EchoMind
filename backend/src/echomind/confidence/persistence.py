"""Content-free confidence input loading and one-Insight short writes."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from echomind.confidence.errors import ConfidenceError, ConfidenceErrorCode
from echomind.confidence.factors import EvidenceFeature, InsightFeatures, derive_evidence_state
from echomind.confidence.schemas import ConfidenceScore, same_utc_instant
from echomind.models import Evidence, Insight, InsightEvidence, Message, Participant
from echomind.models.conversation import conversation_participants


class SessionFactory(Protocol):
    def __call__(self) -> Session: ...


def load_insight_features(
    session: Session,
    insight_id: str,
    *,
    request_id: str,
) -> InsightFeatures | None:
    insight = session.execute(
        select(
            Insight.id,
            Insight.insight_type,
            Insight.status,
            Insight.evidence_state,
            Insight.explicit_self_report,
            Insight.valid_from,
            Insight.valid_to,
            Insight.extraction_version,
            Insight.insight_fingerprint,
            Insight.model_confidence,
            Insight.confidence,
            Insight.confidence_version,
            Insight.confidence_input_fingerprint,
            Insight.confidence_as_of,
            Insight.confidence_calculated_at,
            (func.length(func.trim(Insight.reasoning_basis)) > 0).label("has_reasoning_basis"),
            (func.json_array_length(Insight.alternative_explanations) > 0).label(
                "has_alternative_explanations"
            ),
        ).where(Insight.id == insight_id)
    ).one_or_none()
    if insight is None:
        return None
    linked_ids = list(
        session.scalars(
            select(InsightEvidence.evidence_id)
            .where(InsightEvidence.insight_id == insight_id)
            .order_by(InsightEvidence.evidence_id)
        )
    )
    rows = list(
        session.execute(
            select(
                Evidence.id.label("evidence_id"),
                Evidence.evidence_fingerprint,
                Evidence.evidence_type,
                Evidence.stance,
                Evidence.relevance_score,
                Evidence.is_valid,
                Evidence.invalidated_at,
                Message.id.label("message_id"),
                Message.sender_id,
                Message.conversation_id,
                Message.timestamp,
                Participant.id.label("sender_participant_id"),
            )
            .select_from(InsightEvidence)
            .join(Evidence, Evidence.id == InsightEvidence.evidence_id)
            .join(Message, Message.id == Evidence.message_id)
            .join(Participant, Participant.id == Message.sender_id)
            .where(InsightEvidence.insight_id == insight_id)
            .order_by(Evidence.id)
        ).mappings()
    )
    if len(rows) != len(linked_ids):
        raise ConfidenceError(
            ConfidenceErrorCode.CONFIDENCE_DATA_INCONSISTENT,
            message="The Insight evidence chain is incomplete.",
            request_id=request_id,
            insight_id=insight_id,
            details={"expected": len(linked_ids), "actual": len(rows)},
        )
    memberships: dict[str, dict[str, bool]] = {}
    for row in rows:
        conversation_id = str(row["conversation_id"])
        if conversation_id not in memberships:
            participant_rows = session.execute(
                select(Participant.id, Participant.is_profile_owner)
                .join(
                    conversation_participants,
                    conversation_participants.c.participant_id == Participant.id,
                )
                .where(conversation_participants.c.conversation_id == conversation_id)
            ).all()
            owner_count = sum(bool(item.is_profile_owner) for item in participant_rows)
            if owner_count != 1:
                raise ConfidenceError(
                    ConfidenceErrorCode.PROFILE_OWNER_INCONSISTENT,
                    message="A referenced conversation must have exactly one profile owner.",
                    request_id=request_id,
                    insight_id=insight_id,
                    details={"expected": 1, "actual": owner_count},
                )
            memberships[conversation_id] = {
                str(item.id): bool(item.is_profile_owner) for item in participant_rows
            }
    features: list[EvidenceFeature] = []
    for row in rows:
        conversation_id = str(row["conversation_id"])
        sender_id = str(row["sender_id"])
        membership = memberships[conversation_id]
        if sender_id not in membership or str(row["sender_participant_id"]) != sender_id:
            raise ConfidenceError(
                ConfidenceErrorCode.PROFILE_OWNER_INCONSISTENT,
                message="An evidence sender is inconsistent with its conversation.",
                request_id=request_id,
                insight_id=insight_id,
                details={"expected": "conversation_participant"},
            )
        timestamp = row["timestamp"]
        if timestamp is None:
            raise ConfidenceError(
                ConfidenceErrorCode.EVIDENCE_TIMESTAMP_INVALID,
                message="An evidence message has no timestamp.",
                request_id=request_id,
                insight_id=insight_id,
                details={"expected": "aware_datetime"},
            )
        if not row["is_valid"] and row["invalidated_at"] is None:
            raise ConfidenceError(
                ConfidenceErrorCode.CONFIDENCE_DATA_INCONSISTENT,
                message="Invalid evidence is missing its invalidation timestamp.",
                request_id=request_id,
                insight_id=insight_id,
                details={"expected": "invalidated_at"},
            )
        features.append(
            EvidenceFeature(
                evidence_id=str(row["evidence_id"]),
                evidence_fingerprint=row["evidence_fingerprint"],
                evidence_type=str(row["evidence_type"]),
                stance=row["stance"],
                relevance_score=float(row["relevance_score"]),
                is_valid=bool(row["is_valid"]),
                invalidated_at=row["invalidated_at"],
                message_id=str(row["message_id"]),
                sender_id=sender_id,
                conversation_id=conversation_id,
                timestamp=timestamp,
                is_profile_owner=membership[sender_id],
            )
        )
    evidence_tuple = tuple(features)
    return InsightFeatures(
        insight_id=insight.id,
        insight_type=insight.insight_type,
        status=insight.status,
        evidence_state=derive_evidence_state(evidence_tuple),
        explicit_self_report=insight.explicit_self_report,
        valid_from=insight.valid_from,
        valid_to=insight.valid_to,
        extraction_version=insight.extraction_version,
        insight_fingerprint=insight.insight_fingerprint,
        model_confidence=insight.model_confidence,
        confidence=insight.confidence,
        confidence_version=insight.confidence_version,
        confidence_input_fingerprint=insight.confidence_input_fingerprint,
        confidence_as_of=insight.confidence_as_of,
        confidence_calculated_at=insight.confidence_calculated_at,
        has_reasoning_basis=bool(insight.has_reasoning_basis),
        has_alternative_explanations=bool(insight.has_alternative_explanations),
        evidence=evidence_tuple,
    )


def persist_score(
    session_factory: SessionFactory,
    score: ConfidenceScore,
    *,
    request_id: str,
    force_recalculate: bool,
) -> ConfidenceScore:
    session = session_factory()
    try:
        with session.begin():
            current = session.execute(
                select(
                    Insight.confidence_input_fingerprint,
                    Insight.confidence_version,
                    Insight.confidence_as_of,
                    Insight.evidence_state,
                ).where(Insight.id == score.insight_id)
            ).one_or_none()
            if current is None:
                raise ConfidenceError(
                    ConfidenceErrorCode.INSIGHT_NOT_FOUND,
                    message="The requested Insight no longer exists.",
                    request_id=request_id,
                    insight_id=score.insight_id,
                    recoverable=True,
                )
            unchanged = (
                current.confidence_input_fingerprint == score.confidence_input_fingerprint
                and current.confidence_version == score.confidence_version
                and same_utc_instant(current.confidence_as_of, score.as_of)
                and current.evidence_state is score.evidence_state
            )
            if unchanged and not force_recalculate:
                return score.model_copy(update={"changed": False})
            session.execute(
                update(Insight)
                .where(Insight.id == score.insight_id)
                .values(
                    confidence=score.final_confidence,
                    confidence_version=score.confidence_version,
                    confidence_input_fingerprint=score.confidence_input_fingerprint,
                    confidence_factors_json={
                        **score.factors.model_dump(mode="json"),
                        "minimum_rule_passed": score.minimum_rule_passed,
                        "minimum_rule_code": score.minimum_rule_code.value,
                    },
                    confidence_explanation=score.explanation,
                    confidence_as_of=score.as_of,
                    confidence_calculated_at=score.calculated_at,
                    evidence_state=score.evidence_state,
                )
            )
        return score.model_copy(update={"changed": True})
    except ConfidenceError:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise ConfidenceError(
            ConfidenceErrorCode.PERSISTENCE_FAILED,
            message="The confidence score could not be persisted safely.",
            request_id=request_id,
            insight_id=score.insight_id,
            recoverable=True,
            details={"expected": "single_insight_transaction"},
        ) from None
    finally:
        session.close()

"""Short, window-scoped, idempotent Insight and Evidence persistence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from echomind.extraction.candidate_validation import ValidatedCandidate
from echomind.extraction.errors import ExtractionError, ExtractionErrorCode
from echomind.extraction.evidence import bind_evidence
from echomind.extraction.fingerprints import insight_fingerprint
from echomind.models import Evidence, Insight, InsightEvidence
from echomind.models.enums import EvidenceState, InsightStatus


class SessionFactory(Protocol):
    def __call__(self) -> Session: ...


@dataclass
class PersistenceCounts:
    insights_created: int = 0
    insights_reused: int = 0
    evidence_created: int = 0
    evidence_reused: int = 0
    links_created: int = 0
    links_reused: int = 0


def _persist(
    session: Session,
    candidates: list[ValidatedCandidate],
    *,
    extraction_version: str,
    provider_name: str,
    provider_request_id: str,
    model_name: str,
) -> PersistenceCounts:
    counts = PersistenceCounts()
    for validated in candidates:
        candidate = validated.candidate
        fingerprint = insight_fingerprint(
            extraction_version=extraction_version,
            insight_type=candidate.insight_type.value,
            category=candidate.category.value,
            statement=candidate.statement,
            valid_from=candidate.valid_from,
            valid_to=candidate.valid_to,
        )
        insight = session.scalar(select(Insight).where(Insight.insight_fingerprint == fingerprint))
        if insight is None:
            insight = Insight(
                category=candidate.category.value,
                insight_type=candidate.insight_type,
                title=candidate.title,
                statement=candidate.statement,
                confidence=0.0,
                confidence_version="unscored",
                model_confidence=candidate.model_confidence,
                explicit_self_report=candidate.explicit_self_report,
                status=InsightStatus.PROPOSED,
                evidence_state=EvidenceState.VALID,
                valid_from=candidate.valid_from,
                valid_to=candidate.valid_to,
                model_name=model_name,
                provider_name=provider_name,
                provider_request_id=provider_request_id,
                extraction_version=extraction_version,
                insight_fingerprint=fingerprint,
                reasoning_basis=candidate.reasoning_basis,
                alternative_explanations=list(candidate.alternative_explanations),
                metadata_json={},
            )
            session.add(insight)
            session.flush()
            counts.insights_created += 1
        else:
            counts.insights_reused += 1
        for reference, context_message in validated.evidence:
            bound = bind_evidence(reference, context_message)
            evidence = session.scalar(
                select(Evidence).where(Evidence.evidence_fingerprint == bound.evidence_fingerprint)
            )
            if evidence is None:
                evidence = Evidence(
                    message_id=bound.message_id,
                    excerpt=bound.excerpt,
                    excerpt_start=bound.excerpt_start,
                    excerpt_end=bound.excerpt_end,
                    excerpt_hash=hashlib.sha256(bound.excerpt.encode("utf-8")).hexdigest(),
                    evidence_type=bound.evidence_type,
                    stance=bound.stance,
                    relevance_score=bound.relevance_score,
                    is_valid=True,
                    evidence_fingerprint=bound.evidence_fingerprint,
                )
                session.add(evidence)
                session.flush()
                counts.evidence_created += 1
            else:
                counts.evidence_reused += 1
            link = session.get(InsightEvidence, (insight.id, evidence.id))
            if link is None:
                session.add(InsightEvidence(insight_id=insight.id, evidence_id=evidence.id))
                session.flush()
                counts.links_created += 1
            else:
                counts.links_reused += 1
    return counts


def _known_conflict(session: Session, candidates: list[ValidatedCandidate], version: str) -> bool:
    insight_fingerprints = [
        insight_fingerprint(
            extraction_version=version,
            insight_type=item.candidate.insight_type.value,
            category=item.candidate.category.value,
            statement=item.candidate.statement,
            valid_from=item.candidate.valid_from,
            valid_to=item.candidate.valid_to,
        )
        for item in candidates
    ]
    evidence_fingerprints = [
        bind_evidence(reference, message).evidence_fingerprint
        for item in candidates
        for reference, message in item.evidence
    ]
    return bool(
        session.scalar(
            select(Insight.id).where(Insight.insight_fingerprint.in_(insight_fingerprints)).limit(1)
        )
        or session.scalar(
            select(Evidence.id)
            .where(Evidence.evidence_fingerprint.in_(evidence_fingerprints))
            .limit(1)
        )
    )


def persist_window(
    session_factory: SessionFactory,
    candidates: list[ValidatedCandidate],
    *,
    extraction_version: str,
    provider_name: str,
    provider_request_id: str,
    model_name: str,
    request_id: str,
    window_id: str,
    conversation_id: str,
) -> PersistenceCounts:
    if not candidates:
        return PersistenceCounts()
    for attempt in range(2):
        session = session_factory()
        try:
            with session.begin():
                return _persist(
                    session,
                    candidates,
                    extraction_version=extraction_version,
                    provider_name=provider_name,
                    provider_request_id=provider_request_id,
                    model_name=model_name,
                )
        except IntegrityError:
            session.rollback()
            if attempt == 0 and _known_conflict(session, candidates, extraction_version):
                continue
            raise ExtractionError(
                ExtractionErrorCode.PERSISTENCE_FAILED,
                message="The extraction window could not be persisted safely.",
                request_id=request_id,
                window_id=window_id,
                conversation_id=conversation_id,
                recoverable=True,
                details={"rule": "window_transaction"},
            ) from None
        except SQLAlchemyError:
            session.rollback()
            raise ExtractionError(
                ExtractionErrorCode.PERSISTENCE_FAILED,
                message="The extraction window could not be persisted safely.",
                request_id=request_id,
                window_id=window_id,
                conversation_id=conversation_id,
                recoverable=True,
                details={"rule": "window_transaction"},
            ) from None
        finally:
            session.close()
    raise AssertionError("unreachable")

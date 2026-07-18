"""Synchronous stage-eight confidence orchestration without HTTP or Provider calls."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from echomind.confidence.errors import ConfidenceError, ConfidenceErrorCode
from echomind.confidence.explanations import build_explanation
from echomind.confidence.factors import InsightFeatures, calculate_factors
from echomind.confidence.fingerprints import confidence_input_fingerprint
from echomind.confidence.formula import apply_formula
from echomind.confidence.options import ConfidenceCalculationRequest
from echomind.confidence.persistence import (
    SessionFactory,
    load_insight_features,
    persist_score,
    persist_score_in_session,
)
from echomind.confidence.schemas import (
    ConfidenceErrorRecord,
    ConfidenceReport,
    ConfidenceResult,
    ConfidenceScore,
    MinimumRuleCode,
)
from echomind.db.types import utc_now
from echomind.models.enums import InsightStatus


def calculate_score(
    feature: InsightFeatures,
    *,
    request: ConfidenceCalculationRequest,
    calculated_at: datetime,
) -> ConfidenceScore:
    """Pure calculation: caller supplies both as_of and calculated_at."""
    factors = calculate_factors(
        feature,
        as_of=request.as_of,
        request_id=str(request.request_id),
        calculation_version=request.confidence_version,
    )
    fingerprint = confidence_input_fingerprint(
        feature,
        confidence_version=request.confidence_version,
        as_of=request.as_of,
    )
    factors, passed, rule = apply_formula(feature, factors)
    evidence_state = feature.evidence_state
    explanation = build_explanation(
        insight_type=feature.insight_type,
        evidence_state=evidence_state,
        factors=factors,
        minimum_rule_passed=passed,
        minimum_rule_code=rule,
    )
    return ConfidenceScore(
        insight_id=feature.insight_id,
        confidence_version=request.confidence_version,
        confidence_input_fingerprint=fingerprint,
        evidence_state=evidence_state,
        factors=factors,
        explanation=explanation,
        final_confidence=factors.final_confidence,
        as_of=request.as_of,
        calculated_at=calculated_at,
        minimum_rule_passed=passed,
        minimum_rule_code=rule,
    )


def _error_record(error: ConfidenceError) -> ConfidenceErrorRecord:
    return ConfidenceErrorRecord(
        error_code=error.error_code.value,
        message=error.message,
        request_id=error.request_id,
        insight_id=error.insight_id,
        recoverable=error.recoverable,
        details=error.details,
    )


def _empty_report(request: ConfidenceCalculationRequest) -> ConfidenceReport:
    return ConfidenceReport(
        request_id=request.request_id,
        confidence_version=request.confidence_version,
        as_of=request.as_of,
        requested_count=len(request.insight_ids),
        found_count=0,
        scored_count=0,
        unchanged_count=0,
        skipped_rejected_count=0,
        skipped_superseded_count=0,
        invalid_evidence_count=0,
        minimum_rule_failed_count=0,
        failed_count=0,
        stopped_early=False,
    )


def _skipped(feature: InsightFeatures, report: ConfidenceReport) -> bool:
    if feature.status is InsightStatus.REJECTED:
        report.skipped_rejected_count += 1
        return True
    if feature.status is InsightStatus.SUPERSEDED:
        report.skipped_superseded_count += 1
        return True
    return False


def calculate_confidence(
    session_factory: SessionFactory,
    request: ConfidenceCalculationRequest,
    *,
    calculated_at: datetime | None = None,
) -> ConfidenceReport:
    """Score only explicit IDs, committing each successful Insight independently."""
    effective_calculated_at = calculated_at or utc_now()
    if effective_calculated_at.tzinfo is None or effective_calculated_at.utcoffset() is None:
        raise ValueError("calculated_at must be timezone-aware")
    effective_calculated_at = effective_calculated_at.astimezone(UTC)
    report = _empty_report(request)
    for index, insight_uuid in enumerate(request.insight_ids):
        insight_id = str(insight_uuid)
        feature: InsightFeatures | None = None
        try:
            read_session = session_factory()
            try:
                feature = load_insight_features(
                    read_session,
                    insight_id,
                    request_id=str(request.request_id),
                )
            finally:
                read_session.rollback()
                read_session.close()
            if feature is None:
                raise ConfidenceError(
                    ConfidenceErrorCode.INSIGHT_NOT_FOUND,
                    message="The requested Insight does not exist.",
                    request_id=str(request.request_id),
                    insight_id=insight_id,
                    recoverable=True,
                )
            report.found_count += 1
            include = not (
                (feature.status is InsightStatus.REJECTED and not request.include_rejected)
                or (feature.status is InsightStatus.SUPERSEDED and not request.include_superseded)
            )
            if not include:
                _skipped(feature, report)
                report.results.append(
                    ConfidenceResult(
                        insight_id=insight_id,
                        status=feature.status.value,
                        previous_confidence=feature.confidence,
                        final_confidence=feature.confidence,
                        evidence_state=feature.evidence_state,
                        changed=False,
                        input_fingerprint_changed=False,
                        minimum_rule_passed=False,
                        minimum_rule_code=MinimumRuleCode.NOT_EVALUATED,
                        error_code=ConfidenceErrorCode.INSIGHT_STATUS_SKIPPED.value,
                    )
                )
                continue
            score = calculate_score(
                feature,
                request=request,
                calculated_at=effective_calculated_at,
            )
            fingerprint_changed = (
                feature.confidence_input_fingerprint != score.confidence_input_fingerprint
            )
            persisted = persist_score(
                session_factory,
                score,
                request_id=str(request.request_id),
                force_recalculate=request.force_recalculate,
            )
            report.scored_count += 1
            report.invalid_evidence_count += persisted.factors.invalid_evidence_count
            if not persisted.changed:
                report.unchanged_count += 1
            if not persisted.minimum_rule_passed:
                report.minimum_rule_failed_count += 1
            error_code = None
            if persisted.minimum_rule_code is MinimumRuleCode.CONTRADICTION_ROLES_INCOMPLETE:
                error_code = ConfidenceErrorCode.CONTRADICTION_ROLES_INCOMPLETE.value
            elif not persisted.minimum_rule_passed:
                error_code = ConfidenceErrorCode.MINIMUM_RULE_FAILED.value
            report.results.append(
                ConfidenceResult(
                    insight_id=insight_id,
                    status=feature.status.value,
                    previous_confidence=feature.confidence,
                    final_confidence=persisted.final_confidence,
                    evidence_state=persisted.evidence_state,
                    changed=persisted.changed,
                    input_fingerprint_changed=fingerprint_changed,
                    minimum_rule_passed=persisted.minimum_rule_passed,
                    minimum_rule_code=persisted.minimum_rule_code,
                    error_code=error_code,
                )
            )
        except SQLAlchemyError:
            error = ConfidenceError(
                ConfidenceErrorCode.CONFIDENCE_DATA_INCONSISTENT,
                message="The confidence input could not be read safely.",
                request_id=str(request.request_id),
                insight_id=insight_id,
                recoverable=True,
            )
            report.failed_count += 1
            report.errors.append(_error_record(error))
        except ConfidenceError as error:
            report.failed_count += 1
            report.errors.append(_error_record(error))
        else:
            continue
        report.results.append(
            ConfidenceResult(
                insight_id=insight_id,
                status=feature.status.value if feature else "not_found",
                previous_confidence=feature.confidence if feature else None,
                final_confidence=None,
                evidence_state=feature.evidence_state if feature else None,
                changed=False,
                input_fingerprint_changed=False,
                minimum_rule_passed=False,
                minimum_rule_code=MinimumRuleCode.NOT_EVALUATED,
                error_code=report.errors[-1].error_code,
            )
        )
        if request.stop_on_error:
            report.stopped_early = index < len(request.insight_ids) - 1
            break
    return report


def recalculate_confidence_in_session(
    session: Session,
    insight_id: str,
    *,
    as_of: datetime,
    calculated_at: datetime,
    request_id: str,
) -> ConfidenceScore:
    """Recalculate one Insight inside a caller-owned atomic review transaction."""
    request = ConfidenceCalculationRequest(
        insight_ids=[UUID(insight_id)],
        as_of=as_of,
        force_recalculate=True,
    )
    session.flush()
    feature = load_insight_features(session, insight_id, request_id=request_id)
    if feature is None:
        raise ConfidenceError(
            ConfidenceErrorCode.INSIGHT_NOT_FOUND,
            message="The requested Insight does not exist.",
            request_id=request_id,
            insight_id=insight_id,
        )
    score = calculate_score(feature, request=request, calculated_at=calculated_at)
    return persist_score_in_session(
        session,
        score,
        request_id=request_id,
        force_recalculate=True,
    )

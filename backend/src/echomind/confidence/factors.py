"""Content-free evidence feature snapshots and deterministic factor calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from echomind.confidence.errors import ConfidenceError, ConfidenceErrorCode
from echomind.confidence.schemas import ConfidenceFactors
from echomind.models.enums import EvidenceStance, EvidenceState, InsightStatus, InsightType

D = Decimal
FOUR_PLACES = D("0.0001")


def rounded(value: Decimal) -> float:
    return float(value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP))


def decimal_value(value: float | int) -> Decimal:
    return D(str(value))


@dataclass(frozen=True)
class EvidenceFeature:
    evidence_id: str
    evidence_fingerprint: str | None
    evidence_type: str
    stance: EvidenceStance
    relevance_score: float
    is_valid: bool
    invalidated_at: datetime | None
    message_id: str
    sender_id: str
    conversation_id: str
    timestamp: datetime
    is_profile_owner: bool


@dataclass(frozen=True)
class InsightFeatures:
    insight_id: str
    insight_type: InsightType
    status: InsightStatus
    evidence_state: EvidenceState
    explicit_self_report: bool
    valid_from: datetime | None
    valid_to: datetime | None
    extraction_version: str
    insight_fingerprint: str | None
    model_confidence: float | None
    confidence: float
    confidence_version: str
    confidence_input_fingerprint: str | None
    confidence_as_of: datetime | None
    confidence_calculated_at: datetime | None
    has_reasoning_basis: bool
    has_alternative_explanations: bool
    evidence: tuple[EvidenceFeature, ...]


def derive_evidence_state(evidence: tuple[EvidenceFeature, ...]) -> EvidenceState:
    valid = sum(item.is_valid for item in evidence)
    if valid == 0:
        return EvidenceState.INVALID
    if valid == len(evidence):
        return EvidenceState.VALID
    return EvidenceState.PARTIAL


def _ensure_aware(value: datetime, *, feature: InsightFeatures, request_id: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ConfidenceError(
            ConfidenceErrorCode.EVIDENCE_TIMESTAMP_INVALID,
            message="An evidence timestamp is missing timezone information.",
            request_id=request_id,
            insight_id=feature.insight_id,
            details={"expected": "aware_datetime"},
        )
    return value.astimezone(UTC)


def _quantity(count: int) -> Decimal:
    return {0: D("0"), 1: D("0.25"), 2: D("0.50"), 3: D("0.70"), 4: D("0.85")}.get(count, D("1"))


def _temporal(timestamps: list[datetime]) -> Decimal:
    unique = sorted(set(timestamps))
    if len(unique) < 2:
        return D("0")
    span = unique[-1] - unique[0]
    if span < timedelta(days=1):
        return D("0.15")
    if span < timedelta(days=7):
        return D("0.30")
    if span < timedelta(days=30):
        return D("0.50")
    if span < timedelta(days=90):
        return D("0.75")
    return D("1")


def _context(count: int) -> Decimal:
    return {0: D("0"), 1: D("0.25"), 2: D("0.60"), 3: D("0.80")}.get(count, D("1"))


def _recency(age: timedelta | None) -> Decimal:
    if age is None:
        return D("0")
    if age <= timedelta(days=30):
        return D("1")
    if age <= timedelta(days=90):
        return D("0.85")
    if age <= timedelta(days=180):
        return D("0.70")
    if age <= timedelta(days=365):
        return D("0.50")
    if age <= timedelta(days=730):
        return D("0.25")
    return D("0.10")


def calculate_factors(
    feature: InsightFeatures,
    *,
    as_of: datetime,
    request_id: str,
    calculation_version: str,
) -> ConfidenceFactors:
    """Calculate evidence-only factors; formula fields are initialized for formula.py."""
    as_of_utc = _ensure_aware(as_of, feature=feature, request_id=request_id)
    unique_by_id = {item.evidence_id: item for item in feature.evidence}
    all_evidence = [unique_by_id[key] for key in sorted(unique_by_id)]
    valid = [item for item in all_evidence if item.is_valid]
    timestamps: list[datetime] = []
    aware_timestamps: dict[str, datetime] = {}
    for item in all_evidence:
        if not 0 <= item.relevance_score <= 1:
            raise ConfidenceError(
                ConfidenceErrorCode.EVIDENCE_SCORE_INVALID,
                message="An evidence relevance score is outside the supported range.",
                request_id=request_id,
                insight_id=feature.insight_id,
                details={"expected": "0..1", "actual": item.relevance_score},
            )
        aware_timestamps[item.evidence_id] = _ensure_aware(
            item.timestamp, feature=feature, request_id=request_id
        )
    for item in valid:
        timestamp = aware_timestamps[item.evidence_id]
        if timestamp > as_of_utc:
            raise ConfidenceError(
                ConfidenceErrorCode.EVIDENCE_AFTER_AS_OF,
                message="An evidence timestamp is later than the requested as_of time.",
                request_id=request_id,
                insight_id=feature.insight_id,
                details={"expected": "timestamp<=as_of"},
            )
        timestamps.append(timestamp)

    owner = [item for item in valid if item.is_profile_owner]
    supporting = [item for item in valid if item.stance is EvidenceStance.SUPPORTS]
    contradicting = [item for item in valid if item.stance is EvidenceStance.CONTRADICTS]
    contextual = [item for item in valid if item.stance is EvidenceStance.CONTEXT]
    owner_supporting = [item for item in supporting if item.is_profile_owner]
    if feature.explicit_self_report and owner_supporting:
        explicitness = D("1")
    elif not feature.explicit_self_report and len(owner_supporting) >= 2:
        explicitness = D("0.65")
    elif not feature.explicit_self_report and len(owner_supporting) == 1:
        explicitness = D("0.35")
    else:
        explicitness = D("0")

    total_count = len(all_evidence)
    valid_count = len(valid)
    valid_ratio = D(valid_count) / D(total_count) if total_count else D("0")
    owner_ratio = D(len(owner)) / D(valid_count) if valid_count else D("0")
    non_contextual_ratio = (
        D(len(supporting) + len(contradicting)) / D(valid_count) if valid_count else D("0")
    )
    average_relevance = (
        sum((decimal_value(item.relevance_score) for item in valid), D("0")) / D(valid_count)
        if valid_count
        else D("0")
    )
    quality = (
        D("0.30") * valid_ratio
        + D("0.25") * owner_ratio
        + D("0.20") * non_contextual_ratio
        + D("0.25") * average_relevance
    )
    contradicting_count_tier = {
        0: D("0"),
        1: D("0.35"),
        2: D("0.65"),
    }.get(len(contradicting), D("1"))
    contradicting_ratio = D(len(contradicting)) / D(valid_count) if valid_count else D("0")
    ratio_factor = min(D("1"), contradicting_ratio * D("1.5"))
    contradiction_factor = max(contradicting_count_tier, ratio_factor)
    if supporting and contradicting:
        bilateral = D("1") - (
            D(abs(len(supporting) - len(contradicting))) / D(len(supporting) + len(contradicting))
        )
    else:
        bilateral = D("0")
    newest = max(timestamps) if timestamps else None
    oldest = min(timestamps) if timestamps else None
    temporal = _temporal(timestamps)
    conversations = {item.conversation_id for item in valid}

    return ConfidenceFactors(
        explicitness=rounded(explicitness),
        evidence_quantity=rounded(_quantity(valid_count)),
        temporal_span=rounded(temporal),
        context_diversity=rounded(_context(len(conversations))),
        evidence_quality=rounded(quality),
        recency=rounded(_recency(as_of_utc - newest if newest else None)),
        contradiction_factor=rounded(contradiction_factor),
        bilateral_balance=rounded(bilateral),
        inference_depth_penalty=0.0,
        base_score=0.0,
        positive_contribution=0.0,
        contradiction_penalty=0.0,
        score_before_cap=0.0,
        type_cap=1.0,
        final_confidence=0.0,
        valid_ratio=rounded(valid_ratio),
        owner_ratio=rounded(owner_ratio),
        non_contextual_ratio=rounded(non_contextual_ratio),
        average_relevance=rounded(average_relevance),
        valid_evidence_count=valid_count,
        invalid_evidence_count=total_count - valid_count,
        owner_evidence_count=len(owner),
        supporting_evidence_count=len(supporting),
        contradicting_evidence_count=len(contradicting),
        contextual_evidence_count=len(contextual),
        unique_timestamp_count=len(set(timestamps)),
        unique_conversation_count=len(conversations),
        newest_evidence_at=newest,
        oldest_evidence_at=oldest,
        as_of=as_of_utc,
        calculation_version=calculation_version,
        model_confidence_ignored=True,
    )

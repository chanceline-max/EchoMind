"""Exact confidence-1.0 evidence factors and boundaries."""

from datetime import UTC, datetime, timedelta

import pytest

from echomind.confidence.errors import ConfidenceError
from echomind.confidence.factors import (
    EvidenceFeature,
    calculate_factors,
    derive_evidence_state,
)
from echomind.confidence.schemas import ConfidenceFactors
from echomind.models.enums import EvidenceStance, EvidenceState
from tests.confidence.factories import AS_OF, evidence_feature, insight_features


def factors(
    evidence: tuple[EvidenceFeature, ...] = (), *, explicit: bool = False
) -> ConfidenceFactors:
    feature = insight_features(evidence=evidence, explicit=explicit)
    return calculate_factors(
        feature,
        as_of=AS_OF,
        request_id="request",
        calculation_version="confidence-1.0",
    )


@pytest.mark.parametrize(
    ("evidence", "explicit", "expected"),
    [
        ((evidence_feature(),), True, 1.0),
        ((evidence_feature(0), evidence_feature(1)), False, 0.65),
        ((evidence_feature(),), False, 0.35),
        ((evidence_feature(owner=False),), False, 0.0),
        ((evidence_feature(stance=EvidenceStance.CONTEXT),), True, 0.0),
    ],
)
def test_explicitness(
    evidence: tuple[EvidenceFeature, ...], explicit: bool, expected: float
) -> None:
    assert factors(evidence, explicit=explicit).explicitness == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 0.0), (1, 0.25), (2, 0.5), (3, 0.7), (4, 0.85), (5, 1.0), (10, 1.0)],
)
def test_evidence_quantity(count: int, expected: float) -> None:
    evidence = tuple(evidence_feature(index) for index in range(count))
    assert factors(evidence).evidence_quantity == expected


def test_duplicate_evidence_id_is_counted_once() -> None:
    same = evidence_feature()
    assert factors((same, same)).valid_evidence_count == 1


@pytest.mark.parametrize(
    ("days", "expected"),
    [(None, 0.0), (0.5, 0.15), (1, 0.3), (7, 0.5), (30, 0.75), (90, 1.0)],
)
def test_temporal_span_boundaries(days: float | None, expected: float) -> None:
    first = datetime(2026, 1, 1, tzinfo=UTC)
    evidence: tuple[EvidenceFeature, ...] = (evidence_feature(0, timestamp=first),)
    if days is not None:
        evidence += (evidence_feature(1, timestamp=first + timedelta(days=days)),)
    assert factors(evidence).temporal_span == expected


def test_same_timestamp_is_unique_once() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    result = factors(
        (evidence_feature(0, timestamp=timestamp), evidence_feature(1, timestamp=timestamp))
    )
    assert result.unique_timestamp_count == 1
    assert result.temporal_span == 0.0


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, 0.0), (1, 0.25), (2, 0.6), (3, 0.8), (4, 1.0)],
)
def test_context_diversity(count: int, expected: float) -> None:
    evidence = tuple(evidence_feature(index, conversation=f"c-{index}") for index in range(count))
    assert factors(evidence).context_diversity == expected


def test_quality_exact_formula_and_partial_state() -> None:
    evidence = (
        evidence_feature(0, relevance=1.0),
        evidence_feature(1, owner=False, stance=EvidenceStance.CONTEXT, relevance=0.5),
        evidence_feature(2, valid=False, relevance=1.0),
    )
    result = factors(evidence)
    assert result.valid_ratio == 0.6667
    assert result.owner_ratio == 0.5
    assert result.non_contextual_ratio == 0.5
    assert result.average_relevance == 0.75
    assert result.evidence_quality == 0.6125
    assert derive_evidence_state(evidence) is EvidenceState.PARTIAL


@pytest.mark.parametrize(
    ("age", "expected"),
    [(30, 1.0), (90, 0.85), (180, 0.7), (365, 0.5), (730, 0.25), (731, 0.1)],
)
def test_recency_boundaries(age: int, expected: float) -> None:
    assert factors((evidence_feature(timestamp=AS_OF - timedelta(days=age)),)).recency == expected


@pytest.mark.parametrize("relevance", [-0.1, 1.1])
@pytest.mark.parametrize("valid", [True, False])
def test_invalid_relevance_fails_safely(relevance: float, valid: bool) -> None:
    with pytest.raises(ConfidenceError, match="relevance"):
        factors((evidence_feature(relevance=relevance, valid=valid),))


def test_naive_or_future_timestamp_fails_safely() -> None:
    with pytest.raises(ConfidenceError) as naive:
        factors((evidence_feature(timestamp=datetime(2026, 1, 1)),))
    assert naive.value.error_code.value == "evidence_timestamp_invalid"
    with pytest.raises(ConfidenceError) as future:
        factors((evidence_feature(timestamp=AS_OF + timedelta(seconds=1)),))
    assert future.value.error_code.value == "evidence_after_as_of"


@pytest.mark.parametrize(
    ("contradicting", "expected"),
    [(0, 0.0), (1, 0.75), (2, 1.0), (3, 1.0)],
)
def test_contradiction_factor_uses_max_tier_or_ratio(contradicting: int, expected: float) -> None:
    evidence = (evidence_feature(99),) + tuple(
        evidence_feature(index, stance=EvidenceStance.CONTRADICTS) for index in range(contradicting)
    )
    assert factors(evidence).contradiction_factor == expected


@pytest.mark.parametrize(
    ("supporting", "contradicting", "expected"),
    [(1, 1, 1.0), (2, 1, 0.6667), (3, 1, 0.5), (0, 1, 0.0)],
)
def test_bilateral_balance(supporting: int, contradicting: int, expected: float) -> None:
    evidence = tuple(evidence_feature(index) for index in range(supporting)) + tuple(
        evidence_feature(100 + index, stance=EvidenceStance.CONTRADICTS)
        for index in range(contradicting)
    )
    assert factors(evidence).bilateral_balance == expected

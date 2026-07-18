"""Formula, type caps, minimum rules, fingerprints and explanations."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from echomind.confidence.explanations import build_explanation
from echomind.confidence.factors import InsightFeatures, calculate_factors
from echomind.confidence.fingerprints import confidence_input_fingerprint
from echomind.confidence.formula import BASE_SCORES, DEPTH_PENALTIES, TYPE_CAPS, apply_formula
from echomind.confidence.schemas import ConfidenceFactors, MinimumRuleCode
from echomind.models.enums import EvidenceStance, EvidenceState, InsightType
from tests.confidence.factories import AS_OF, evidence_feature, insight_features


def scored(
    feature: InsightFeatures,
) -> tuple[ConfidenceFactors, bool, MinimumRuleCode]:
    base = calculate_factors(
        feature,
        as_of=AS_OF,
        request_id="request",
        calculation_version="confidence-1.0",
    )
    return apply_formula(feature, base)


@pytest.mark.parametrize(
    ("insight_type", "base", "penalty", "cap"),
    [
        (InsightType.FACT, 0.20, 0.00, 0.95),
        (InsightType.PREFERENCE, 0.18, 0.02, 0.90),
        (InsightType.PATTERN, 0.16, 0.04, 0.85),
        (InsightType.INFERENCE, 0.12, 0.08, 0.80),
        (InsightType.HYPOTHESIS, 0.08, 0.12, 0.60),
        (InsightType.CONTRADICTION, 0.16, 0.04, 0.90),
        (InsightType.CHANGE, 0.16, 0.04, 0.85),
    ],
)
def test_versioned_type_constants(
    insight_type: InsightType, base: float, penalty: float, cap: float
) -> None:
    assert float(BASE_SCORES[insight_type]) == base
    assert float(DEPTH_PENALTIES[insight_type]) == penalty
    assert float(TYPE_CAPS[insight_type]) == cap


@pytest.mark.parametrize("insight_type", list(InsightType))
def test_each_type_respects_cap_and_four_place_rounding(insight_type: InsightType) -> None:
    evidence = tuple(
        evidence_feature(index, conversation=f"c-{index}", relevance=1.0) for index in range(5)
    )
    if insight_type is InsightType.CONTRADICTION:
        evidence = tuple(
            evidence_feature(
                index,
                conversation=f"c-{index}",
                stance=(EvidenceStance.SUPPORTS if index < 2 else EvidenceStance.CONTRADICTS),
                relevance=1.0,
            )
            for index in range(4)
        )
    feature = insight_features(insight_type=insight_type, evidence=evidence)
    if insight_type is InsightType.CHANGE:
        feature = replace(
            feature,
            valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            valid_to=datetime(2026, 7, 1, tzinfo=UTC),
        )
    result, passed, _ = scored(feature)
    assert passed
    assert result.final_confidence <= float(TYPE_CAPS[insight_type])
    assert result.final_confidence == round(result.final_confidence, 4)


@pytest.mark.parametrize("insight_type", list(InsightType))
def test_each_type_has_monotonic_low_medium_and_full_evidence(
    insight_type: InsightType,
) -> None:
    def build(count: int) -> InsightFeatures:
        items = []
        for index in range(count):
            stance = EvidenceStance.SUPPORTS
            if insight_type is InsightType.CONTRADICTION and index % 2:
                stance = EvidenceStance.CONTRADICTS
            items.append(
                evidence_feature(
                    index,
                    stance=stance,
                    conversation=f"c-{index}",
                    relevance=1.0,
                )
            )
        feature = insight_features(insight_type=insight_type, evidence=tuple(items))
        if insight_type is InsightType.CHANGE:
            feature = replace(
                feature,
                valid_from=datetime(2026, 1, 1, tzinfo=UTC),
                valid_to=datetime(2026, 7, 1, tzinfo=UTC),
            )
        return feature

    minimum_count = (
        2
        if insight_type
        in {
            InsightType.PATTERN,
            InsightType.CONTRADICTION,
            InsightType.CHANGE,
        }
        else 1
    )
    low = scored(build(minimum_count))[0].final_confidence
    medium = scored(build(3 if minimum_count == 1 else 4))[0].final_confidence
    full = scored(build(5 if minimum_count == 1 else 6))[0].final_confidence
    assert 0 <= low <= medium <= full <= float(TYPE_CAPS[insight_type])


def test_contradicting_evidence_penalizes_normal_type_but_not_contradiction() -> None:
    base_evidence = (evidence_feature(0), evidence_feature(1))
    opposed = base_evidence + (evidence_feature(2, stance=EvidenceStance.CONTRADICTS),)
    ordinary, _, _ = scored(insight_features(evidence=base_evidence))
    ordinary_opposed, _, _ = scored(insight_features(evidence=opposed))
    contradiction, _, _ = scored(
        insight_features(insight_type=InsightType.CONTRADICTION, evidence=opposed)
    )
    assert ordinary_opposed.final_confidence < ordinary.final_confidence
    assert ordinary_opposed.contradiction_penalty > 0
    assert contradiction.contradiction_penalty == 0


@pytest.mark.parametrize(
    ("feature", "code"),
    [
        (insight_features(explicit=False), MinimumRuleCode.FACT_SELF_REPORT_REQUIREMENT_FAILED),
        (
            insight_features(insight_type=InsightType.PREFERENCE, explicit=False),
            MinimumRuleCode.PREFERENCE_SUPPORT_REQUIREMENT_FAILED,
        ),
        (
            insight_features(insight_type=InsightType.PATTERN, explicit=False),
            MinimumRuleCode.PATTERN_EVIDENCE_REQUIREMENT_FAILED,
        ),
        (
            insight_features(insight_type=InsightType.INFERENCE, has_reasoning_basis=False),
            MinimumRuleCode.INFERENCE_REASONING_REQUIREMENT_FAILED,
        ),
        (
            insight_features(
                insight_type=InsightType.HYPOTHESIS, has_alternative_explanations=False
            ),
            MinimumRuleCode.HYPOTHESIS_ALTERNATIVES_REQUIREMENT_FAILED,
        ),
        (
            insight_features(insight_type=InsightType.CONTRADICTION),
            MinimumRuleCode.CONTRADICTION_ROLES_INCOMPLETE,
        ),
        (
            insight_features(insight_type=InsightType.CHANGE),
            MinimumRuleCode.CHANGE_TIME_REQUIREMENT_FAILED,
        ),
    ],
)
def test_minimum_rule_failures_are_zero_without_type_changes(
    feature: InsightFeatures, code: MinimumRuleCode
) -> None:
    result, passed, actual = scored(feature)
    assert not passed
    assert actual is code
    assert result.final_confidence == 0.0


def test_all_invalid_evidence_forces_zero() -> None:
    feature = insight_features(evidence=(evidence_feature(valid=False),))
    result, passed, code = scored(feature)
    assert result.final_confidence == 0.0
    assert not passed
    assert code is MinimumRuleCode.EVIDENCE_INVALID


def test_additional_minimum_rule_boundaries() -> None:
    fact_other = insight_features(evidence=(evidence_feature(owner=False),))
    assert scored(fact_other)[2] is MinimumRuleCode.FACT_SELF_REPORT_REQUIREMENT_FAILED

    same_time = datetime(2026, 1, 1, tzinfo=UTC)
    pattern = insight_features(
        insight_type=InsightType.PATTERN,
        evidence=(
            evidence_feature(0, timestamp=same_time),
            evidence_feature(1, timestamp=same_time),
        ),
    )
    assert scored(pattern)[2] is MinimumRuleCode.PATTERN_TIME_REQUIREMENT_FAILED

    inference = insight_features(
        insight_type=InsightType.INFERENCE,
        has_alternative_explanations=False,
    )
    assert scored(inference)[2] is MinimumRuleCode.INFERENCE_ALTERNATIVES_REQUIREMENT_FAILED

    change = insight_features(
        insight_type=InsightType.CHANGE,
        evidence=(evidence_feature(0), evidence_feature(1)),
    )
    assert scored(change)[2] is MinimumRuleCode.CHANGE_RANGE_REQUIREMENT_FAILED


def test_model_confidence_does_not_change_formula_or_fingerprint() -> None:
    low = insight_features(model_confidence=0.1)
    high = replace(low, model_confidence=0.9)
    assert scored(low)[0] == scored(high)[0]
    assert confidence_input_fingerprint(
        low, confidence_version="confidence-1.0", as_of=AS_OF
    ) == confidence_input_fingerprint(high, confidence_version="confidence-1.0", as_of=AS_OF)


@pytest.mark.parametrize(
    "change",
    [
        lambda f: replace(f, insight_type=InsightType.PREFERENCE),
        lambda f: replace(f, explicit_self_report=False),
        lambda f: replace(f, valid_from=datetime(2026, 1, 1, tzinfo=UTC)),
        lambda f: replace(f, extraction_version="candidate-extraction-2.0"),
        lambda f: replace(f, evidence=(replace(f.evidence[0], is_valid=False),)),
        lambda f: replace(f, evidence=(replace(f.evidence[0], stance=EvidenceStance.CONTRADICTS),)),
        lambda f: replace(f, evidence=(replace(f.evidence[0], relevance_score=0.2),)),
        lambda f: replace(
            f,
            evidence=(
                replace(f.evidence[0], timestamp=f.evidence[0].timestamp - timedelta(days=1)),
            ),
        ),
        lambda f: replace(f, evidence=(replace(f.evidence[0], conversation_id="changed"),)),
        lambda f: replace(f, evidence=(replace(f.evidence[0], sender_id="changed"),)),
        lambda f: replace(f, evidence=(replace(f.evidence[0], is_profile_owner=False),)),
    ],
)
def test_material_inputs_change_fingerprint(
    change: Callable[[InsightFeatures], InsightFeatures],
) -> None:
    feature = insight_features()
    original = confidence_input_fingerprint(
        feature, confidence_version="confidence-1.0", as_of=AS_OF
    )
    changed = confidence_input_fingerprint(
        change(feature), confidence_version="confidence-1.0", as_of=AS_OF
    )
    assert changed != original


def test_as_of_and_version_change_fingerprint() -> None:
    feature = insight_features()
    original = confidence_input_fingerprint(
        feature, confidence_version="confidence-1.0", as_of=AS_OF
    )
    assert original != confidence_input_fingerprint(
        feature, confidence_version="confidence-1.0", as_of=AS_OF + timedelta(seconds=1)
    )
    assert original != confidence_input_fingerprint(
        feature, confidence_version="confidence-1.1", as_of=AS_OF
    )


@pytest.mark.parametrize("insight_type", [InsightType.HYPOTHESIS, InsightType.CONTRADICTION])
def test_explanation_is_safe_and_type_specific(insight_type: InsightType) -> None:
    evidence = (
        evidence_feature(0),
        evidence_feature(1, stance=EvidenceStance.CONTRADICTS),
    )
    feature = insight_features(insight_type=insight_type, evidence=evidence)
    factors, passed, code = scored(feature)
    value = build_explanation(
        insight_type=insight_type,
        evidence_state=EvidenceState.VALID,
        factors=factors,
        minimum_rule_passed=passed,
        minimum_rule_code=code,
    )
    assert "模型自评未参与" in value
    assert "科学概率" in value
    assert (
        "0.60" in value
        if insight_type is InsightType.HYPOTHESIS
        else "不代表其中某一方正确" in value
    )
    for forbidden in ["RAW_PRIVATE", "Synthetic title marker", "message-0", "C:\\private"]:
        assert forbidden not in value

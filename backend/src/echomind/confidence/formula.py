"""Exact confidence-1.0 weights, minimum rules, caps, and rounding."""

from decimal import Decimal

from echomind.confidence.factors import InsightFeatures, decimal_value, rounded
from echomind.confidence.schemas import ConfidenceFactors, MinimumRuleCode
from echomind.models.enums import InsightType

D = Decimal

BASE_SCORES = {
    InsightType.FACT: D("0.20"),
    InsightType.PREFERENCE: D("0.18"),
    InsightType.PATTERN: D("0.16"),
    InsightType.INFERENCE: D("0.12"),
    InsightType.HYPOTHESIS: D("0.08"),
    InsightType.CONTRADICTION: D("0.16"),
    InsightType.CHANGE: D("0.16"),
}
DEPTH_PENALTIES = {
    InsightType.FACT: D("0.00"),
    InsightType.PREFERENCE: D("0.02"),
    InsightType.PATTERN: D("0.04"),
    InsightType.INFERENCE: D("0.08"),
    InsightType.HYPOTHESIS: D("0.12"),
    InsightType.CONTRADICTION: D("0.04"),
    InsightType.CHANGE: D("0.04"),
}
TYPE_CAPS = {
    InsightType.FACT: D("0.95"),
    InsightType.PREFERENCE: D("0.90"),
    InsightType.PATTERN: D("0.85"),
    InsightType.INFERENCE: D("0.80"),
    InsightType.HYPOTHESIS: D("0.60"),
    InsightType.CONTRADICTION: D("0.90"),
    InsightType.CHANGE: D("0.85"),
}


def minimum_rule(
    feature: InsightFeatures, factors: ConfidenceFactors
) -> tuple[bool, MinimumRuleCode]:
    if derive_invalid(factors):
        return False, MinimumRuleCode.EVIDENCE_INVALID
    insight_type = feature.insight_type
    if insight_type is InsightType.FACT:
        if not feature.explicit_self_report or factors.explicitness != 1.0:
            return False, MinimumRuleCode.FACT_SELF_REPORT_REQUIREMENT_FAILED
    elif insight_type is InsightType.PREFERENCE:
        if not feature.explicit_self_report and factors.owner_evidence_count < 2:
            return False, MinimumRuleCode.PREFERENCE_SUPPORT_REQUIREMENT_FAILED
    elif insight_type is InsightType.PATTERN:
        if factors.valid_evidence_count < 2:
            return False, MinimumRuleCode.PATTERN_EVIDENCE_REQUIREMENT_FAILED
        if factors.unique_timestamp_count < 2:
            return False, MinimumRuleCode.PATTERN_TIME_REQUIREMENT_FAILED
    elif insight_type is InsightType.INFERENCE:
        if not feature.has_reasoning_basis:
            return False, MinimumRuleCode.INFERENCE_REASONING_REQUIREMENT_FAILED
        if not feature.has_alternative_explanations:
            return False, MinimumRuleCode.INFERENCE_ALTERNATIVES_REQUIREMENT_FAILED
    elif insight_type is InsightType.HYPOTHESIS:
        if not feature.has_reasoning_basis:
            return False, MinimumRuleCode.HYPOTHESIS_REASONING_REQUIREMENT_FAILED
        if not feature.has_alternative_explanations:
            return False, MinimumRuleCode.HYPOTHESIS_ALTERNATIVES_REQUIREMENT_FAILED
    elif insight_type is InsightType.CONTRADICTION:
        if not factors.supporting_evidence_count or not factors.contradicting_evidence_count:
            return False, MinimumRuleCode.CONTRADICTION_ROLES_INCOMPLETE
    elif insight_type is InsightType.CHANGE:
        if factors.unique_timestamp_count < 2:
            return False, MinimumRuleCode.CHANGE_TIME_REQUIREMENT_FAILED
        if (
            feature.valid_from is None
            or feature.valid_to is None
            or feature.valid_to < feature.valid_from
        ):
            return False, MinimumRuleCode.CHANGE_RANGE_REQUIREMENT_FAILED
    return True, MinimumRuleCode.PASSED


def derive_invalid(factors: ConfidenceFactors) -> bool:
    return factors.valid_evidence_count == 0


def apply_formula(
    feature: InsightFeatures, factors: ConfidenceFactors
) -> tuple[ConfidenceFactors, bool, MinimumRuleCode]:
    insight_type = feature.insight_type
    values = {
        "explicitness": decimal_value(factors.explicitness),
        "evidence_quantity": decimal_value(factors.evidence_quantity),
        "temporal_span": decimal_value(factors.temporal_span),
        "context_diversity": decimal_value(factors.context_diversity),
        "evidence_quality": decimal_value(factors.evidence_quality),
        "recency": decimal_value(factors.recency),
        "bilateral_balance": decimal_value(factors.bilateral_balance),
    }
    leading = (
        values["bilateral_balance"]
        if insight_type is InsightType.CONTRADICTION
        else values["explicitness"]
    )
    positive = (
        D("0.20") * leading
        + D("0.15") * values["evidence_quantity"]
        + D("0.12") * values["temporal_span"]
        + D("0.10") * values["context_diversity"]
        + D("0.10") * values["evidence_quality"]
        + D("0.08") * values["recency"]
    )
    contradiction_penalty = (
        D("0")
        if insight_type is InsightType.CONTRADICTION
        else D("0.25") * decimal_value(factors.contradiction_factor)
    )
    base = BASE_SCORES[insight_type]
    depth = DEPTH_PENALTIES[insight_type]
    cap = TYPE_CAPS[insight_type]
    raw = base + positive - depth - contradiction_penalty
    before_cap = max(D("0"), raw)
    passed, code = minimum_rule(feature, factors)
    final = min(before_cap, cap) if passed else D("0")
    return (
        factors.model_copy(
            update={
                "inference_depth_penalty": rounded(depth),
                "base_score": rounded(base),
                "positive_contribution": rounded(positive),
                "contradiction_penalty": rounded(contradiction_penalty),
                "score_before_cap": rounded(before_cap),
                "type_cap": rounded(cap),
                "final_confidence": rounded(final),
            }
        ),
        passed,
        code,
    )

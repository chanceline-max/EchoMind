"""Synthetic Profile source graphs with no real conversation content."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from echomind.models import Evidence, Insight
from echomind.models.enums import EvidenceStance, EvidenceState, InsightStatus, InsightType
from echomind.profiling.options import ProfileGenerationRequest
from tests.review.factories import create_review_graph


@dataclass(frozen=True)
class ProfileGraph:
    insights: list[Insight]
    evidence: list[Evidence]


def profile_request(**changes: object) -> ProfileGenerationRequest:
    values: dict[str, object] = {
        "request_id": UUID("00000000-0000-0000-0000-000000000010"),
        "generated_as_of": datetime(2026, 7, 21, 12, tzinfo=UTC),
    }
    values.update(changes)
    return ProfileGenerationRequest.model_validate(values)


def create_profile_graph(session: Session) -> ProfileGraph:
    insights: list[Insight] = []
    evidence: list[Evidence] = []
    definitions = (
        ("1", InsightType.FACT, "background", EvidenceState.VALID, 0.0),
        ("2", InsightType.PREFERENCE, "preference", EvidenceState.PARTIAL, 0.42),
        ("3", InsightType.CONTRADICTION, "other", EvidenceState.VALID, 0.71),
        ("4", InsightType.HYPOTHESIS, "other", EvidenceState.VALID, 0.32),
        ("5", InsightType.PATTERN, "thinking_pattern", EvidenceState.INVALID, 0.0),
    )
    for suffix, insight_type, category, state, confidence in definitions:
        graph = create_review_graph(
            session,
            insight_count=1,
            evidence_count=2,
            status=InsightStatus.CONFIRMED,
            conversation_suffix=suffix,
        )
        insight = graph.insights[0]
        insight.insight_type = insight_type
        insight.category = category
        insight.title = f"Synthetic Profile title {suffix}"
        insight.statement = f"Synthetic Profile statement {suffix}."
        insight.confidence = confidence
        insight.confidence_version = "confidence-1.0"
        insight.confidence_explanation = "Synthetic mechanical support explanation."
        insight.confidence_factors_json = {
            "minimum_rule_passed": state != EvidenceState.INVALID,
            "minimum_rule_code": "passed" if state != EvidenceState.INVALID else "pattern_minimum",
        }
        insight.evidence_state = state
        insight.revision_number = int(suffix)
        if insight_type in {InsightType.HYPOTHESIS, InsightType.CONTRADICTION}:
            insight.reasoning_basis = "Synthetic local reasoning basis."
            insight.alternative_explanations = ["Synthetic alternative explanation."]
        if state == EvidenceState.PARTIAL:
            graph.evidence[1].is_valid = False
            graph.evidence[1].invalidated_at = datetime(2026, 7, 20, tzinfo=UTC)
            graph.evidence[1].invalidation_reasons_json = ["source_message_excluded"]
        if state == EvidenceState.INVALID:
            for item in graph.evidence:
                item.is_valid = False
                item.invalidated_at = datetime(2026, 7, 20, tzinfo=UTC)
                item.invalidation_reasons_json = ["source_message_excluded"]
        if insight_type == InsightType.CONTRADICTION:
            graph.evidence[1].stance = EvidenceStance.CONTRADICTS
        insights.append(insight)
        evidence.extend(graph.evidence)
    session.commit()
    return ProfileGraph(insights=insights, evidence=evidence)

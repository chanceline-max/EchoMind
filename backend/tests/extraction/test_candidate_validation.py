"""Mechanical semantic boundaries for all seven candidate types."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from echomind.extraction.candidate_validation import validate_candidate
from echomind.extraction.errors import ExtractionError
from echomind.extraction.schemas import CandidateInsightBatch
from echomind.extraction.windows import ContextWindow
from tests.extraction.factories import candidate, evidence_ref
from tests.extraction.test_schemas_and_windows import _messages


def window() -> ContextWindow:
    return ContextWindow.from_messages(
        conversation_id="conversation-db-id",
        messages=_messages(4),
        extraction_version="candidate-extraction-1.1",
    )


def validated(payload: dict[str, object]) -> object:
    item = CandidateInsightBatch.model_validate({"candidates": [payload]}, strict=True).candidates[
        0
    ]
    return validate_candidate(item, window(), candidate_index=0)


@pytest.mark.parametrize(
    "payload",
    [
        candidate(),
        candidate(insight_type="preference"),
        candidate(
            insight_type="pattern",
            refs=[evidence_ref("m001"), evidence_ref("m003")],
            explicit=False,
        ),
        candidate(
            insight_type="inference",
            reasoning_basis="A bounded synthetic reason.",
            alternative_explanations=["Another synthetic explanation."],
            explicit=False,
        ),
        candidate(
            insight_type="hypothesis",
            reasoning_basis="A tentative synthetic reason.",
            alternative_explanations=["A different synthetic cause."],
            explicit=False,
        ),
        candidate(
            insight_type="contradiction",
            refs=[evidence_ref("m001"), evidence_ref("m003", "contradicting")],
            explicit=False,
        ),
        candidate(
            insight_type="change",
            refs=[evidence_ref("m001"), evidence_ref("m003")],
            valid_from=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            valid_to=datetime(2026, 1, 3, tzinfo=UTC).isoformat(),
            explicit=False,
        ),
    ],
    ids=["fact", "preference", "pattern", "inference", "hypothesis", "contradiction", "change"],
)
def test_valid_candidate_types(payload: dict[str, object]) -> None:
    assert validated(payload) is not None


@pytest.mark.parametrize(
    ("payload", "rule"),
    [
        (candidate(explicit=False), "fact_explicit_self_report"),
        (candidate(refs=[evidence_ref("m002")]), "profile_owner_evidence"),
        (
            candidate(insight_type="preference", explicit=False),
            "preference_support",
        ),
        (
            candidate(insight_type="pattern", explicit=False),
            "pattern_distinct_messages",
        ),
        (
            candidate(
                insight_type="inference",
                reasoning_basis="reason",
                explicit=False,
            ),
            "inference_alternatives",
        ),
        (
            candidate(
                insight_type="hypothesis",
                reasoning_basis=None,
                alternative_explanations=["alternative"],
                explicit=False,
            ),
            "hypothesis_reasoning",
        ),
        (
            candidate(
                insight_type="contradiction",
                refs=[evidence_ref("m001"), evidence_ref("m003")],
                explicit=False,
            ),
            "contradiction_roles",
        ),
        (
            candidate(
                insight_type="change",
                refs=[evidence_ref("m001"), evidence_ref("m003")],
                explicit=False,
            ),
            "change_valid_range",
        ),
        (candidate(refs=[evidence_ref("m999")]), "evidence_inside_window"),
    ],
)
def test_invalid_candidate_rules(payload: dict[str, object], rule: str) -> None:
    with pytest.raises(ExtractionError) as error:
        validated(payload)
    assert error.value.details["rule"] == rule


def test_duplicate_evidence_reference_is_rejected_by_schema() -> None:
    ref = evidence_ref("m001")
    with pytest.raises(ValidationError):
        CandidateInsightBatch.model_validate(
            {"candidates": [candidate(refs=[ref, ref])]},
            strict=True,
        )

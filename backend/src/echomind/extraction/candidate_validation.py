"""Minimum mechanical evidence rules; not a psychological truth validator."""

from __future__ import annotations

from dataclasses import dataclass

from echomind.extraction.errors import ExtractionError, ExtractionErrorCode
from echomind.extraction.schemas import (
    CandidateEvidenceRef,
    CandidateEvidenceRole,
    CandidateInsight,
)
from echomind.extraction.windows import ContextWindow, ContextWindowMessage
from echomind.models.enums import InsightType


@dataclass(frozen=True)
class ValidatedCandidate:
    candidate: CandidateInsight
    evidence: list[tuple[CandidateEvidenceRef, ContextWindowMessage]]


def _reject(
    window: ContextWindow,
    candidate_index: int,
    rule: str,
    *,
    code: ExtractionErrorCode = ExtractionErrorCode.CANDIDATE_SEMANTIC_RULE_FAILED,
) -> ExtractionError:
    return ExtractionError(
        code,
        message="A candidate did not satisfy the extraction evidence contract.",
        request_id="candidate-validation",
        window_id=window.window_id,
        conversation_id=window.conversation_id,
        recoverable=True,
        details={"rule": rule, "candidate_index": candidate_index},
    )


def validate_candidate(
    candidate: CandidateInsight,
    window: ContextWindow,
    *,
    candidate_index: int,
    request_id: str = "candidate-validation",
) -> ValidatedCandidate:
    messages = window.message_by_alias()
    resolved: list[tuple[CandidateEvidenceRef, ContextWindowMessage]] = []
    for reference in candidate.evidence_refs:
        message = messages.get(reference.context_message_id)
        if message is None:
            raise _reject(
                window,
                candidate_index,
                "evidence_inside_window",
                code=ExtractionErrorCode.CANDIDATE_EVIDENCE_OUTSIDE_WINDOW,
            )
        resolved.append((reference, message))
    if any(not message.evidence_content for _, message in resolved):
        error = _reject(window, candidate_index, "evidence_content_non_empty")
        error.request_id = request_id
        raise error
    owner = [(reference, message) for reference, message in resolved if message.is_profile_owner]
    if not owner:
        raise _reject(window, candidate_index, "profile_owner_evidence")
    distinct_messages = {message.database_message_id for _, message in resolved}
    distinct_times = {message.timestamp for _, message in resolved}
    insight_type = candidate.insight_type
    if insight_type is InsightType.FACT:
        if not candidate.explicit_self_report:
            raise _reject(window, candidate_index, "fact_explicit_self_report")
        if not any(
            reference.role is CandidateEvidenceRole.SUPPORTING and message.is_profile_owner
            for reference, message in resolved
        ):
            raise _reject(window, candidate_index, "fact_owner_supporting")
    elif insight_type is InsightType.PREFERENCE:
        owner_messages = {message.database_message_id for _, message in owner}
        if not candidate.explicit_self_report and len(owner_messages) < 2:
            raise _reject(window, candidate_index, "preference_support")
    elif insight_type is InsightType.PATTERN:
        if len(distinct_messages) < 2:
            raise _reject(window, candidate_index, "pattern_distinct_messages")
        if len(distinct_times) < 2:
            raise _reject(window, candidate_index, "pattern_distinct_times")
    elif insight_type in {InsightType.INFERENCE, InsightType.HYPOTHESIS}:
        prefix = insight_type.value
        if candidate.reasoning_basis is None:
            raise _reject(window, candidate_index, f"{prefix}_reasoning")
        if not candidate.alternative_explanations:
            raise _reject(window, candidate_index, f"{prefix}_alternatives")
    elif insight_type is InsightType.CONTRADICTION:
        roles = {reference.role for reference, _ in resolved}
        if len(distinct_messages) < 2:
            raise _reject(window, candidate_index, "contradiction_distinct_messages")
        if not {
            CandidateEvidenceRole.SUPPORTING,
            CandidateEvidenceRole.CONTRADICTING,
        }.issubset(roles):
            raise _reject(window, candidate_index, "contradiction_roles")
    elif insight_type is InsightType.CHANGE:
        if len(distinct_times) < 2:
            raise _reject(window, candidate_index, "change_distinct_times")
        if candidate.valid_from is None or candidate.valid_to is None:
            raise _reject(window, candidate_index, "change_valid_range")
    return ValidatedCandidate(candidate=candidate, evidence=resolved)

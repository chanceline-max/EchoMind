"""Local Evidence construction from persisted normalized content only."""

from __future__ import annotations

from dataclasses import dataclass

from echomind.extraction.fingerprints import evidence_fingerprint
from echomind.extraction.schemas import CandidateEvidenceRef, CandidateEvidenceRole
from echomind.extraction.windows import TRUNCATION_MARKER, ContextWindowMessage
from echomind.models.enums import EvidenceStance

MAX_EVIDENCE_CHARACTERS = 500


@dataclass(frozen=True)
class BoundEvidence:
    message_id: str
    excerpt: str
    excerpt_start: int
    excerpt_end: int
    evidence_type: str
    stance: EvidenceStance
    relevance_score: float
    evidence_fingerprint: str


def _excerpt(content: str) -> tuple[str, int]:
    if not content:
        raise ValueError("evidence content must not be empty")
    if len(content) <= MAX_EVIDENCE_CHARACTERS:
        return content, len(content)
    prefix_length = MAX_EVIDENCE_CHARACTERS - len(TRUNCATION_MARKER)
    return f"{content[:prefix_length]}{TRUNCATION_MARKER}", prefix_length


def bind_evidence(
    reference: CandidateEvidenceRef,
    message: ContextWindowMessage,
) -> BoundEvidence:
    excerpt, source_end = _excerpt(message.evidence_content)
    stance = {
        CandidateEvidenceRole.SUPPORTING: EvidenceStance.SUPPORTS,
        CandidateEvidenceRole.CONTRADICTING: EvidenceStance.CONTRADICTS,
        CandidateEvidenceRole.CONTEXTUAL: EvidenceStance.CONTEXT,
    }[reference.role]
    evidence_type = reference.role.value
    return BoundEvidence(
        message_id=message.database_message_id,
        excerpt=excerpt,
        excerpt_start=0,
        excerpt_end=source_end,
        evidence_type=evidence_type,
        stance=stance,
        relevance_score=reference.relevance_score,
        evidence_fingerprint=evidence_fingerprint(
            message_id=message.database_message_id,
            evidence_type=evidence_type,
            excerpt=excerpt,
        ),
    )

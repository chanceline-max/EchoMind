"""Dense contract matrices for routing, fingerprints, and stable serialization."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from echomind.models.enums import EvidenceState, InsightStatus, InsightType
from echomind.profiling import fingerprints
from echomind.profiling.document import build_profile
from echomind.profiling.options import ProfileGenerationRequest
from echomind.profiling.sections import route_section, sort_section_items
from echomind.repositories.profile_repository import ProfileInsightSource, load_profile_sources
from tests.profiling.factories import create_profile_graph, profile_request


@pytest.mark.parametrize(
    ("category", "insight_type", "evidence_state", "expected"),
    [
        ("background", InsightType.FACT, EvidenceState.VALID, "background"),
        ("preference", InsightType.FACT, EvidenceState.VALID, "preferences"),
        ("thinking_pattern", InsightType.PATTERN, EvidenceState.VALID, "thinking_patterns"),
        ("behavior_execution", InsightType.PATTERN, EvidenceState.VALID, "behavior_execution"),
        ("emotional_response", InsightType.PATTERN, EvidenceState.VALID, "emotional_responses"),
        (
            "relationship_pattern",
            InsightType.PATTERN,
            EvidenceState.VALID,
            "relationship_patterns",
        ),
        ("values_motivation", InsightType.FACT, EvidenceState.VALID, "values_motivation"),
        ("internal_conflict", InsightType.INFERENCE, EvidenceState.VALID, "internal_conflicts"),
        ("background", InsightType.CHANGE, EvidenceState.VALID, "temporal_changes"),
        ("background", InsightType.CONTRADICTION, EvidenceState.VALID, "contradictions"),
        ("background", InsightType.HYPOTHESIS, EvidenceState.VALID, "hypotheses"),
        ("background", InsightType.FACT, EvidenceState.INVALID, "invalidated"),
        ("other", InsightType.INFERENCE, EvidenceState.VALID, "other_confirmed"),
    ],
)
def test_section_routing_priority_matrix(
    db_session: Session,
    category: str,
    insight_type: InsightType,
    evidence_state: EvidenceState,
    expected: str,
) -> None:
    create_profile_graph(db_session)
    source = load_profile_sources(db_session, profile_request())[0]
    candidate = replace(
        source,
        category=category,
        insight_type=insight_type,
        evidence_state=evidence_state,
    )
    assert route_section(candidate) == expected


def test_section_sorting_is_stable_and_uses_documented_keys(db_session: Session) -> None:
    create_profile_graph(db_session)
    source = load_profile_sources(db_session, profile_request())[0]
    later = replace(source, id="later", confidence=0.2)
    earlier = replace(source, id="earlier", confidence=0.8)
    rows = [later, earlier]
    sort_section_items("background", rows)
    assert [row.id for row in rows] == ["earlier", "later"]

    changed_later = replace(source, id="change-later", valid_from=datetime(2026, 2, 1, tzinfo=UTC))
    changed_earlier = replace(
        source, id="change-earlier", valid_from=datetime(2026, 1, 1, tzinfo=UTC)
    )
    changes = [changed_later, changed_earlier]
    sort_section_items("temporal_changes", changes)
    assert [row.id for row in changes] == ["change-earlier", "change-later"]


def _replace_source(
    sources: list[ProfileInsightSource], replacement: ProfileInsightSource
) -> list[ProfileInsightSource]:
    return [replacement if item.id == replacement.id else item for item in sources]


@pytest.mark.parametrize(
    "mutation",
    [
        "revision",
        "status",
        "title",
        "statement",
        "type",
        "category",
        "confidence",
        "evidence_state",
        "evidence_validity",
        "evidence_relevance",
        "evidence_role",
        "evidence_fingerprint",
    ],
)
def test_source_fingerprint_change_matrix(db_session: Session, mutation: str) -> None:
    create_profile_graph(db_session)
    request = profile_request()
    sources = load_profile_sources(db_session, request)
    _, before = fingerprints.build_source_manifest(sources, request)
    source = sources[0]
    evidence = source.evidence[0]
    if mutation == "revision":
        changed = replace(source, revision_number=source.revision_number + 1)
    elif mutation == "status":
        changed = replace(source, status=InsightStatus.REJECTED)
    elif mutation == "title":
        changed = replace(source, title=f"{source.title} changed")
    elif mutation == "statement":
        changed = replace(source, statement=f"{source.statement} changed")
    elif mutation == "type":
        changed = replace(source, insight_type=InsightType.CHANGE)
    elif mutation == "category":
        changed = replace(source, category="values_motivation")
    elif mutation == "confidence":
        changed = replace(source, confidence=0.1234)
    elif mutation == "evidence_state":
        changed = replace(
            source,
            evidence_state=(
                EvidenceState.PARTIAL
                if source.evidence_state != EvidenceState.PARTIAL
                else EvidenceState.VALID
            ),
        )
    else:
        if mutation == "evidence_validity":
            changed_evidence = replace(evidence, is_valid=not evidence.is_valid)
        elif mutation == "evidence_relevance":
            changed_evidence = replace(evidence, relevance_score=0.1234)
        elif mutation == "evidence_role":
            changed_evidence = replace(evidence, role="context")
        else:
            changed_evidence = replace(evidence, evidence_fingerprint="f" * 64)
        changed = replace(source, evidence=(changed_evidence, *source.evidence[1:]))
    _, after = fingerprints.build_source_manifest(_replace_source(sources, changed), request)
    assert after != before


@pytest.mark.parametrize(
    "changed_request",
    [
        profile_request(evidence_mode="excerpts"),
        profile_request(include_reasoning=False),
        profile_request(include_partial_evidence=False),
        profile_request(include_invalidated=False),
        profile_request(generated_as_of=datetime(2026, 7, 22, tzinfo=UTC)),
    ],
)
def test_generation_fingerprint_changes_with_every_supported_option(
    db_session: Session, changed_request: ProfileGenerationRequest
) -> None:
    create_profile_graph(db_session)
    request = profile_request()
    sources = load_profile_sources(db_session, request)
    _, source_hash = fingerprints.build_source_manifest(sources, request)
    assert fingerprints.generation_fingerprint(
        source_hash, changed_request
    ) != fingerprints.generation_fingerprint(source_hash, request)


def test_generation_fingerprint_covers_renderer_and_schema_versions(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_profile_graph(db_session)
    request = profile_request()
    sources = load_profile_sources(db_session, request)
    _, source_hash = fingerprints.build_source_manifest(sources, request)
    before = fingerprints.generation_fingerprint(source_hash, request)
    monkeypatch.setattr(fingerprints, "MARKDOWN_RENDERER_VERSION", "profile-markdown-test")
    assert fingerprints.generation_fingerprint(source_hash, request) != before

    schema_request = ProfileGenerationRequest.model_construct(
        **{**request.__dict__, "profile_schema_version": "echo-profile-document-test"}
    )
    assert fingerprints.generation_fingerprint(source_hash, schema_request) != before


def test_document_output_is_byte_stable_and_rejects_non_finite_data(db_session: Session) -> None:
    create_profile_graph(db_session)
    request = profile_request()
    sources = load_profile_sources(db_session, request)
    generated_at = datetime(2026, 7, 21, 12, tzinfo=UTC)
    first = build_profile(sources, request, generated_at=generated_at)
    second = build_profile(sources, request, generated_at=generated_at)
    assert first.json_content.encode() == second.json_content.encode()
    assert first.markdown_content.encode() == second.markdown_content.encode()
    with pytest.raises(ValueError):
        fingerprints.canonical_bytes({"not_finite": float("nan")})


def test_generated_as_of_normalizes_to_utc_without_changing_instant() -> None:
    request = profile_request(generated_as_of=datetime(2026, 7, 21, 20, tzinfo=UTC) + timedelta(0))
    assert request.generated_as_of == datetime(2026, 7, 21, 20, tzinfo=UTC)

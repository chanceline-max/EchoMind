"""Selection, routing, references, renderers, and fingerprint contracts."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from echomind.models.enums import InsightStatus
from echomind.profiling.document import build_profile
from echomind.profiling.fingerprints import build_source_manifest
from echomind.profiling.markdown import escape_markdown
from echomind.profiling.options import ProfileGenerationRequest
from echomind.profiling.sections import SECTION_DEFINITIONS
from echomind.repositories.profile_repository import load_profile_sources
from tests.profiling.factories import create_profile_graph, profile_request


def test_request_is_strict_utc_and_selected_ids_are_stably_deduplicated() -> None:
    selected = uuid4()
    request = profile_request(scope="selected_confirmed", selected_insight_ids=[selected, selected])
    assert request.selected_insight_ids == [selected]
    assert request.generated_as_of.tzinfo == UTC
    with pytest.raises(ValidationError):
        ProfileGenerationRequest.model_validate(
            {
                "request_id": uuid4(),
                "scope": "selected_confirmed",
                "selected_insight_ids": [],
                "generated_as_of": datetime(2026, 1, 1, tzinfo=UTC),
            }
        )
    with pytest.raises(ValidationError):
        profile_request(unknown=True)


def test_confirmed_only_selection_keeps_zero_confidence_and_rejects_bad_selected(
    db_session: Session,
) -> None:
    graph = create_profile_graph(db_session)
    graph.insights[1].status = InsightStatus.PROPOSED
    db_session.commit()
    selected = load_profile_sources(db_session, profile_request())
    assert graph.insights[0].id in {item.id for item in selected}
    assert all(item.status == InsightStatus.CONFIRMED for item in selected)
    assert any(item.confidence == 0 for item in selected)
    with pytest.raises(Exception, match="confirmed"):
        load_profile_sources(
            db_session,
            profile_request(
                scope="selected_confirmed", selected_insight_ids=[graph.insights[1].id]
            ),
        )


def test_sections_references_and_evidence_modes_are_deterministic(db_session: Session) -> None:
    graph = create_profile_graph(db_session)
    sources = load_profile_sources(db_session, profile_request())
    generated_at = datetime(2026, 7, 21, 12, 1, tzinfo=UTC)
    references = build_profile(sources, profile_request(), generated_at=generated_at)
    repeated = build_profile(list(reversed(sources)), profile_request(), generated_at=generated_at)
    assert references.json_content == repeated.json_content
    assert references.markdown_content == repeated.markdown_content
    assert [item.section_key for item in references.document.sections] == [
        item[0] for item in SECTION_DEFINITIONS
    ]
    all_items = [item for section in references.document.sections for item in section.items]
    assert len(all_items) == len(graph.insights)
    assert len({item.insight_id for item in all_items}) == len(all_items)
    assert [item.profile_insight_ref for item in all_items] == [
        f"I{index:03d}" for index in range(1, len(all_items) + 1)
    ]
    assert references.document.metadata.evidence_count == len(
        {item.evidence_id for item in references.document.evidence_index}
    )
    assert all(item.excerpt is None for item in references.document.evidence_index)

    excerpts_request = profile_request(evidence_mode="excerpts")
    excerpts = build_profile(sources, excerpts_request, generated_at=generated_at)
    assert all(item.excerpt is not None for item in excerpts.document.evidence_index)
    assert "Synthetic review excerpt" not in references.markdown_content
    assert "Synthetic review excerpt" in excerpts.markdown_content


def test_partial_invalid_and_reasoning_options(db_session: Session) -> None:
    create_profile_graph(db_session)
    sources = load_profile_sources(db_session, profile_request())
    built = build_profile(
        sources,
        profile_request(
            include_partial_evidence=False,
            include_invalidated=False,
            include_reasoning=False,
        ),
        generated_at=datetime(2026, 7, 21, 12, 2, tzinfo=UTC),
    )
    assert built.document.metadata.excluded_count == 2
    assert not next(
        section for section in built.document.sections if section.section_key == "invalidated"
    ).items
    assert all(
        item.reasoning_basis is None and not item.alternative_explanations
        for section in built.document.sections
        for item in section.items
    )
    displayed_count = sum(len(section.items) for section in built.document.sections)
    assert f"- Insight 数量：{displayed_count}\n" in built.markdown_content


def test_markdown_is_safe_stable_utf8_lf_and_json_round_trips(db_session: Session) -> None:
    graph = create_profile_graph(db_session)
    graph.insights[0].title = "# title <script> [x](https://example.test)"
    graph.insights[0].statement = "- item `code` <iframe> https://example.test 😀"
    db_session.commit()
    sources = load_profile_sources(db_session, profile_request())
    built = build_profile(
        sources,
        profile_request(),
        generated_at=datetime(2026, 7, 21, 12, 3, tzinfo=UTC),
    )
    assert "<script>" not in built.markdown_content
    assert "<iframe>" not in built.markdown_content
    assert "](https://" not in built.markdown_content
    assert "https://example" not in built.markdown_content
    assert "\r" not in built.markdown_content
    assert built.markdown_content.endswith("\n") and not built.markdown_content.endswith("\n\n")
    payload = json.loads(built.json_content)
    assert payload["metadata"]["document_hash"] == built.document.metadata.document_hash
    assert "😀" in built.json_content
    assert escape_markdown("<b> https://x.test") == "&lt;b&gt; https&#58;//x.test"


def test_source_fingerprint_changes_only_for_relevant_profile_inputs(db_session: Session) -> None:
    graph = create_profile_graph(db_session)
    request = profile_request()
    sources = load_profile_sources(db_session, request)
    manifest, before = build_source_manifest(sources, request)
    graph.insights[0].model_confidence = 0.01
    db_session.commit()
    _, unrelated = build_source_manifest(load_profile_sources(db_session, request), request)
    assert unrelated == before
    graph.insights[0].statement = "Updated synthetic statement."
    db_session.commit()
    after_manifest, after = build_source_manifest(
        load_profile_sources(db_session, request), request
    )
    assert after != before
    before_by_id = {item.insight_id: item for item in manifest}
    after_by_id = {item.insight_id: item for item in after_manifest}
    assert (
        after_by_id[graph.insights[0].id].content_fingerprint
        != before_by_id[graph.insights[0].id].content_fingerprint
    )


def test_profile_source_query_does_not_read_message_bodies(db_session: Session) -> None:
    create_profile_graph(db_session)
    statements: list[str] = []
    engine = db_session.get_bind()
    assert isinstance(engine, Engine)

    def capture_sql(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        del connection, cursor, parameters, context, executemany
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture_sql)
    try:
        load_profile_sources(db_session, profile_request())
    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)
    source_queries = [statement for statement in statements if "join messages" in statement]
    assert source_queries
    assert all("raw_content" not in statement for statement in source_queries)
    assert all("normalized_content" not in statement for statement in source_queries)

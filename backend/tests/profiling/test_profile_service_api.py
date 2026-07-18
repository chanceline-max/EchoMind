"""Snapshot idempotency, integrity, staleness, immutability, and API exports."""

from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from echomind.core.config import Settings
from echomind.db.session import create_db_engine, create_session_factory
from echomind.models import ProfileSnapshot
from echomind.models.enums import EvidenceState, InsightStatus
from echomind.profiling import service as profile_service
from echomind.profiling.document import build_profile
from echomind.profiling.errors import ProfileError
from echomind.profiling.persistence import to_snapshot
from echomind.profiling.service import detect_staleness, generate_profile, read_document
from echomind.repositories import profile_repository
from echomind.repositories.profile_repository import get_snapshot, load_profile_sources
from tests.profiling.factories import create_profile_graph, profile_request


def test_snapshot_generation_is_idempotent_and_staleness_is_dynamic(
    db_session: Session, settings: Settings
) -> None:
    graph = create_profile_graph(db_session)
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    request = profile_request()
    first, created = generate_profile(
        factory,
        request,
        settings=settings,
        generated_at=datetime(2026, 7, 21, 13, tzinfo=UTC),
    )
    second, created_again = generate_profile(
        factory,
        request,
        settings=settings,
        generated_at=datetime(2026, 7, 21, 14, tzinfo=UTC),
    )
    assert created is True and created_again is False
    assert first.id == second.id
    assert db_session.scalar(select(func.count()).select_from(ProfileSnapshot)) == 1
    original_json = dict(first.json_content)
    graph.insights[0].statement = "A later synthetic revision."
    graph.insights[0].revision_number += 1
    db_session.commit()
    status = detect_staleness(db_session, first)
    assert status.current_source_status == "stale"
    assert "insight_revision_changed" in status.stale_reason_codes
    assert first.json_content == original_json


def test_snapshot_integrity_and_orm_immutability(db_session: Session, settings: Settings) -> None:
    create_profile_graph(db_session)
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    snapshot, _ = generate_profile(factory, profile_request(), settings=settings)
    assert read_document(snapshot).metadata.profile_id == snapshot.id
    managed = get_snapshot(db_session, snapshot.id)
    assert managed is not None
    managed.json_content = {"tampered": True}
    with pytest.raises(ValueError, match="immutable"):
        db_session.commit()
    db_session.rollback()
    stored = get_snapshot(db_session, snapshot.id)
    assert stored is not None
    stored.json_content["metadata"]["profile_version"] = "tampered"
    with pytest.raises(ProfileError, match="integrity"):
        read_document(stored)
    db_session.rollback()
    with pytest.raises(ValueError, match="immutable"):
        db_session.delete(stored)
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("revision", "insight_revision_changed"),
        ("status", "confirmed_set_changed"),
        ("confidence", "confidence_changed"),
        ("evidence_invalidated", "evidence_changed"),
        ("evidence_restored", "evidence_changed"),
        ("new_confirmed", "confirmed_set_changed"),
    ],
)
def test_staleness_change_matrix(
    db_session: Session,
    settings: Settings,
    mutation: str,
    expected_reason: str,
) -> None:
    graph = create_profile_graph(db_session)
    if mutation == "new_confirmed":
        graph.insights[4].status = InsightStatus.PROPOSED
        db_session.commit()
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    snapshot, _ = generate_profile(factory, profile_request(), settings=settings)
    original_json = dict(snapshot.json_content)
    original_markdown = snapshot.markdown_content
    original_hash = snapshot.document_hash
    if mutation == "revision":
        graph.insights[0].revision_number += 1
    elif mutation == "status":
        graph.insights[0].status = InsightStatus.REJECTED
    elif mutation == "confidence":
        graph.insights[0].confidence = 0.1234
    elif mutation == "evidence_invalidated":
        graph.evidence[0].is_valid = False
        graph.evidence[0].invalidated_at = datetime(2026, 7, 21, tzinfo=UTC)
        graph.evidence[0].invalidation_reasons_json = ["source_message_excluded"]
    elif mutation == "evidence_restored":
        graph.evidence[3].is_valid = True
        graph.evidence[3].invalidated_at = None
        graph.evidence[3].invalidation_reasons_json = []
    else:
        graph.insights[4].status = InsightStatus.CONFIRMED
    db_session.commit()
    result = detect_staleness(db_session, snapshot)
    assert result.current_source_status == "stale"
    assert expected_reason in result.stale_reason_codes
    assert all("Synthetic" not in code for code in result.stale_reason_codes)
    assert snapshot.json_content == original_json
    assert snapshot.markdown_content == original_markdown
    assert snapshot.document_hash == original_hash


def test_selected_profile_ignores_unselected_insight_changes(
    db_session: Session, settings: Settings
) -> None:
    graph = create_profile_graph(db_session)
    request = profile_request(
        scope="selected_confirmed", selected_insight_ids=[graph.insights[0].id]
    )
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    snapshot, _ = generate_profile(factory, request, settings=settings)
    graph.insights[1].statement = "An unrelated synthetic statement revision."
    graph.insights[1].revision_number += 1
    db_session.commit()
    assert detect_staleness(db_session, snapshot).current_source_status == "current"


def test_renderer_failure_does_not_save_partial_snapshot(
    db_session: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_profile_graph(db_session)
    factory = create_session_factory(cast(Engine, db_session.get_bind()))

    def fail_render(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic renderer failure")

    monkeypatch.setattr(profile_service, "build_profile", fail_render)
    with pytest.raises(RuntimeError, match="synthetic renderer failure"):
        generate_profile(factory, profile_request(), settings=settings)
    assert db_session.scalar(select(func.count()).select_from(ProfileSnapshot)) == 0


def test_concurrent_unique_conflict_safely_reuses_existing_snapshot(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_profile_graph(db_session)
    request = profile_request()
    built = build_profile(
        load_profile_sources(db_session, request),
        request,
        generated_at=datetime(2026, 7, 21, 13, tzinfo=UTC),
    )
    factory = create_session_factory(cast(Engine, db_session.get_bind()))
    with factory() as first_session:
        existing, created = profile_repository.add_snapshot(first_session, to_snapshot(built))
    assert created is True

    original_find = profile_repository.find_by_generation_fingerprint
    lookup_count = 0

    def race_find(session: Session, generation_fingerprint: str) -> ProfileSnapshot | None:
        nonlocal lookup_count
        lookup_count += 1
        if lookup_count == 1:
            return None
        return original_find(session, generation_fingerprint)

    monkeypatch.setattr(profile_repository, "find_by_generation_fingerprint", race_find)
    with factory() as racing_session:
        reused, created_again = profile_repository.add_snapshot(racing_session, to_snapshot(built))
    assert created_again is False
    assert reused.id == existing.id
    assert lookup_count == 2
    assert db_session.scalar(select(func.count()).select_from(ProfileSnapshot)) == 1


pytestmark = pytest.mark.anyio
ORIGIN = {"Origin": "http://localhost:5173"}


def seed_api(settings: Settings) -> None:
    engine = create_db_engine(settings.database_url)
    session = create_session_factory(engine)()
    try:
        create_profile_graph(session)
    finally:
        session.close()
        engine.dispose()


async def test_profile_api_create_reuse_list_detail_and_exports(
    client: AsyncClient, settings: Settings
) -> None:
    seed_api(settings)
    body = profile_request().model_dump(mode="json")
    created = await client.post("/api/v1/profiles", json=body, headers=ORIGIN)
    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    profile_id = created.json()["profile_snapshot_id"]
    reused = await client.post("/api/v1/profiles", json=body, headers=ORIGIN)
    assert reused.status_code == 200
    assert reused.json()["reused"] is True

    listing = await client.get("/api/v1/profiles")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert "json_content" not in listing.text
    detail = await client.get(f"/api/v1/profiles/{profile_id}")
    assert detail.status_code == 200
    assert detail.json()["document"]["metadata"]["selection_policy"] == "confirmed-only-1.0"
    assert "raw_content" not in detail.text
    assert "canonical_name" not in detail.text

    markdown = await client.get(f"/api/v1/profiles/{profile_id}/markdown")
    assert markdown.status_code == 200
    assert markdown.headers["content-type"] == "text/markdown; charset=utf-8"
    assert "attachment;" in markdown.headers["content-disposition"]
    assert markdown.headers["x-content-type-options"] == "nosniff"
    exported_json = await client.get(f"/api/v1/profiles/{profile_id}/json")
    assert exported_json.status_code == 200
    assert exported_json.headers["content-type"] == "application/json; charset=utf-8"
    assert exported_json.json() == detail.json()["document"]


async def test_profile_api_security_errors_origin_and_no_destructive_routes(
    client: AsyncClient, settings: Settings
) -> None:
    seed_api(settings)
    denied = await client.post(
        "/api/v1/profiles",
        json=profile_request().model_dump(mode="json"),
        headers={"Origin": "https://untrusted.example"},
    )
    assert denied.status_code == 403
    missing = await client.get("/api/v1/profiles/missing")
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"
    for method in (client.patch, client.delete):
        response = await method("/api/v1/profiles/missing", headers=ORIGIN)
        assert response.status_code in {404, 405}


async def test_profile_api_handles_empty_source_and_legacy_snapshot_safely(
    client: AsyncClient, settings: Settings
) -> None:
    empty = await client.post(
        "/api/v1/profiles",
        json=profile_request().model_dump(mode="json"),
        headers=ORIGIN,
    )
    assert empty.status_code == 422
    assert empty.json()["error_code"] == "no_confirmed_insights"

    engine = create_db_engine(settings.database_url)
    with create_session_factory(engine)() as session:
        session.add(
            ProfileSnapshot(
                id="00000000-0000-0000-0000-000000000099",
                generated_at=datetime(2026, 7, 20, tzinfo=UTC),
                profile_version="legacy-profile",
                schema_version="legacy-schema",
                markdown_content="# Legacy synthetic profile\n",
                json_content={"legacy": True},
                source_range_start=None,
                source_range_end=None,
                statistics={},
                limitations=[],
                evidence_state=EvidenceState.VALID,
                invalidated_at=None,
                metadata_json={},
            )
        )
        session.commit()
    engine.dispose()

    listing = await client.get("/api/v1/profiles")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["current_source_status"] == "source_unavailable"
    assert listing.json()["items"][0]["stale_reason_codes"] == ["source_missing"]

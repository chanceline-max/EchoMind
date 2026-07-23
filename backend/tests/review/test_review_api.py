"""HTTP contracts for local Insight review and safe traceability."""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from echomind.core.config import Settings
from echomind.db.session import create_db_engine, create_session_factory
from echomind.models import Insight
from tests.review.factories import ReviewGraph, create_review_graph

pytestmark = pytest.mark.anyio
ORIGIN = {"Origin": "http://localhost:5173"}


def seeded_graph(settings: Settings) -> ReviewGraph:
    engine = create_db_engine(settings.database_url)
    session: Session = create_session_factory(engine)()
    try:
        return create_review_graph(session)
    finally:
        session.close()
        engine.dispose()


async def test_list_filters_and_detail_are_aggregated_and_private(
    client: AsyncClient,
    settings: Settings,
) -> None:
    graph = seeded_graph(settings)
    response = await client.get(
        "/api/v1/insights",
        params={"status": "proposed", "category": "background"},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["evidence_count"] == 2
    assert body["items"][0]["valid_evidence_count"] == 2

    detail = await client.get(f"/api/v1/insights/{graph.insights[0].id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["evidence"][0]["sender_role"] == "PROFILE_OWNER"
    assert payload["evidence"][0]["message_link"].startswith("/conversations/")
    assert "raw_content" not in detail.text
    assert "canonical_name" not in detail.text
    assert "E:\\" not in detail.text


async def test_confirm_and_revision_history_use_expected_revision(
    client: AsyncClient,
    settings: Settings,
) -> None:
    graph = seeded_graph(settings)
    insight_id = graph.insights[0].id
    confirmed = await client.post(
        f"/api/v1/insights/{insight_id}/confirm",
        json={"expected_revision": 0, "note": "Reviewed locally."},
        headers=ORIGIN,
    )
    assert confirmed.status_code == 200
    assert confirmed.headers["cache-control"] == "no-store"
    assert confirmed.json()["insight"]["status"] == "confirmed"
    assert confirmed.json()["insight"]["revision_number"] == 1

    stale = await client.post(
        f"/api/v1/insights/{insight_id}/confirm",
        json={"expected_revision": 0},
        headers=ORIGIN,
    )
    assert stale.status_code == 409
    assert stale.json()["error_code"] == "insight_revision_conflict"
    assert stale.json()["details"]["current_revision"] == 1

    history = await client.get(f"/api/v1/insights/{insight_id}/revisions")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["action"] == "confirmed"


async def test_batch_confirm_is_private_origin_checked_and_writes_each_revision(
    client: AsyncClient,
    settings: Settings,
) -> None:
    graph = seeded_graph(settings)
    engine = create_db_engine(settings.database_url)
    session: Session = create_session_factory(engine)()
    try:
        for insight in graph.insights:
            stored = session.get(Insight, insight.id)
            assert stored is not None
            stored.confidence = 0.8
        session.commit()
    finally:
        session.close()
        engine.dispose()

    response = await client.post(
        "/api/v1/insights/batch-confirm",
        json={
            "items": [
                {"insight_id": insight.id, "expected_revision": 0} for insight in graph.insights
            ]
        },
        headers=ORIGIN,
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "confirmed_ids": [insight.id for insight in graph.insights],
        "confirmed_count": 2,
    }

    untrusted = await client.post(
        "/api/v1/insights/batch-confirm",
        json={"items": [{"insight_id": graph.insights[0].id, "expected_revision": 1}]},
        headers={"Origin": "https://untrusted.example"},
    )
    assert untrusted.status_code == 403


async def test_patch_rejects_confidence_and_unknown_fields(
    client: AsyncClient,
    settings: Settings,
) -> None:
    graph = seeded_graph(settings)
    insight_id = graph.insights[0].id
    response = await client.patch(
        f"/api/v1/insights/{insight_id}",
        json={"expected_revision": 0, "confidence": 0.99},
        headers=ORIGIN,
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_request"


async def test_write_allows_cli_without_origin_and_rejects_untrusted_origin(
    client: AsyncClient,
    settings: Settings,
) -> None:
    graph = seeded_graph(settings)
    insight_id = graph.insights[0].id
    cli_response = await client.post(
        f"/api/v1/insights/{insight_id}/confirm",
        json={"expected_revision": 0},
    )
    assert cli_response.status_code == 200

    browser_response = await client.post(
        f"/api/v1/insights/{insight_id}/reject",
        json={"expected_revision": 1, "note": "Synthetic rejection reason."},
        headers={"Origin": "https://untrusted.example"},
    )
    assert browser_response.status_code == 403
    assert browser_response.json()["error_code"] == "origin_not_allowed"


async def test_message_location_and_destructive_routes(
    client: AsyncClient,
    settings: Settings,
) -> None:
    graph = seeded_graph(settings)
    message = graph.messages[2]
    response = await client.get(f"/api/v1/messages/{message.id}/location")
    assert response.status_code == 200
    assert response.json() == {
        "message_id": message.id,
        "conversation_id": message.conversation_id,
        "zero_based_index": 2,
        "suggested_offset": 0,
    }
    assert response.headers["cache-control"] == "no-store"

    for path in (
        f"/api/v1/insights/{graph.insights[0].id}",
        f"/api/v1/evidence/{graph.evidence[0].id}",
        f"/api/v1/insight-revisions/{graph.insights[0].id}",
    ):
        deleted = await client.delete(path, headers=ORIGIN)
        assert deleted.status_code in {404, 405}

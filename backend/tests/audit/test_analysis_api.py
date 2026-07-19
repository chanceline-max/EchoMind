"""Stage 11 audit coverage for the minimal user-reachable analysis boundary."""

import json
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient

from echomind.confidence.options import ConfidenceCalculationRequest
from echomind.confidence.schemas import ConfidenceErrorRecord, ConfidenceReport
from echomind.core.config import Settings
from echomind.db.base import Base
from echomind.main import create_app
from echomind.providers import LLMProvider, create_provider
from echomind.services import analysis_service

pytestmark = pytest.mark.anyio


def chat_bytes() -> bytes:
    return json.dumps(
        {
            "format": "echomind-generic-chat",
            "version": "1.0",
            "platform": "synthetic-stage-eleven",
            "conversations": [
                {
                    "id": "audit-conversation",
                    "title": "Synthetic audit conversation",
                    "participants": [
                        {"id": "owner", "name": "Synthetic Owner", "is_profile_owner": True}
                    ],
                    "messages": [
                        {
                            "id": "audit-message-1",
                            "sender_id": "owner",
                            "timestamp": "2026-07-18T08:00:00+08:00",
                            "type": "text",
                            "content": "Synthetic audit statement.",
                        }
                    ],
                }
            ],
        }
    ).encode()


def candidate_payload() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "insight_type": "fact",
                "category": "background",
                "title": "Synthetic audit candidate",
                "statement": "The synthetic owner reports an audit fact.",
                "evidence_refs": [
                    {"context_message_id": "m001", "role": "supporting", "relevance_score": 0.9}
                ],
                "model_confidence": 0.7,
                "explicit_self_report": True,
                "reasoning_basis": None,
                "alternative_explanations": [],
                "valid_from": None,
                "valid_to": None,
            }
        ]
    }


async def make_client(
    tmp_path: Path,
    *,
    provider_factory: Callable[[Settings], LLMProvider] | None = None,
    settings_updates: dict[str, Any] | None = None,
) -> AsyncIterator[AsyncClient]:
    (tmp_path / "uploads").mkdir(exist_ok=True)
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'analysis-api.db').as_posix()}",
        import_temp_root=str(tmp_path / "uploads"),
        **(settings_updates or {}),
    )
    kwargs = {} if provider_factory is None else {"analysis_provider_factory": provider_factory}
    app = create_app(settings, **kwargs)
    Base.metadata.create_all(app.state.engine)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client
    finally:
        app.state.engine.dispose()


async def import_conversation(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/imports",
        files={"file": ("synthetic-audit.json", chat_bytes())},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 201
    conversations = await client.get(response.json()["links"]["conversations"])
    return cast(str, conversations.json()["items"][0]["id"])


async def test_capabilities_are_safe_no_store_and_default_mock_available(tmp_path: Path) -> None:
    async for client in make_client(tmp_path):
        response = await client.get("/api/v1/analysis/capabilities")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "configured_provider": "mock",
            "provider_available": True,
            "remote_provider": False,
            "remote_consent_required": False,
            "extraction_version": "candidate-extraction-1.1",
            "confidence_version": "confidence-1.0",
            "max_conversations_per_request": 100,
        }
        serialized = response.text.casefold()
        for forbidden in ("api_key", "endpoint", "authorization", "prompt", "database"):
            assert forbidden not in serialized


async def test_default_mock_analysis_returns_empty_candidates_without_network(
    tmp_path: Path,
) -> None:
    async for client in make_client(tmp_path):
        conversation_id = await import_conversation(client)
        response = await client.post(
            "/api/v1/analysis",
            json={"conversation_ids": [conversation_id], "remote_consent": False},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert body["candidates_received"] == 0
        assert body["insight_ids"] == []
        assert body["confidence_scored_count"] == 0


async def test_injected_mock_creates_scores_and_reuses_one_evidence_bound_insight(
    tmp_path: Path,
) -> None:
    def provider_factory(settings: Settings) -> LLMProvider:
        return create_provider(
            settings, provider_name="mock", mock_response_payload=candidate_payload()
        )

    async for client in make_client(tmp_path, provider_factory=provider_factory):
        conversation_id = await import_conversation(client)
        payload = {"conversation_ids": [conversation_id], "remote_consent": False}
        headers = {"Origin": "http://localhost:5173"}
        first = await client.post("/api/v1/analysis", json=payload, headers=headers)
        second = await client.post("/api/v1/analysis", json=payload, headers=headers)
        assert first.status_code == second.status_code == 200
        first_body, second_body = first.json(), second.json()
        assert first_body["insights_created"] == 1
        assert first_body["confidence_scored_count"] == 1
        assert len(first_body["insight_ids"]) == 1
        assert second_body["insights_created"] == 0
        assert second_body["insights_reused"] == 1
        assert second_body["insight_ids"] == first_body["insight_ids"]
        insight = await client.get(f"/api/v1/insights/{first_body['insight_ids'][0]}")
        assert insight.status_code == 200
        assert len(insight.json()["evidence"]) == 1
        assert insight.json()["confidence_version"] == "confidence-1.0"


async def test_analysis_rejects_bad_origin_and_remote_without_consent(tmp_path: Path) -> None:
    async for client in make_client(tmp_path):
        conversation_id = await import_conversation(client)
        rejected = await client.post(
            "/api/v1/analysis",
            json={"conversation_ids": [conversation_id]},
            headers={"Origin": "https://example.invalid"},
        )
        assert rejected.status_code == 403

    remote = {
        "llm_provider": "openai_compatible",
        "llm_remote_enabled": True,
        "llm_openai_compatible_endpoint": "https://model.example.invalid/v1/chat/completions",
        "llm_openai_compatible_api_key": "synthetic-test-key",
        "llm_openai_compatible_model": "synthetic-model",
    }
    async for client in make_client(tmp_path, settings_updates=remote):
        rejected = await client.post(
            "/api/v1/analysis",
            json={"conversation_ids": ["00000000-0000-4000-8000-000000000001"]},
            headers={"Origin": "http://localhost:5173"},
        )
        assert rejected.status_code == 422
        assert rejected.json()["error_code"] == "remote_consent_required"
        assert rejected.headers["cache-control"] == "no-store"


async def test_confidence_partial_failure_is_reported_and_keeps_created_insight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def provider_factory(settings: Settings) -> LLMProvider:
        return create_provider(
            settings, provider_name="mock", mock_response_payload=candidate_payload()
        )

    def fail_confidence(
        session_factory: object,
        request: ConfidenceCalculationRequest,
        *,
        calculated_at: datetime | None = None,
    ) -> ConfidenceReport:
        del session_factory, calculated_at
        insight_id = str(request.insight_ids[0])
        return ConfidenceReport(
            request_id=request.request_id,
            confidence_version=request.confidence_version,
            as_of=request.as_of,
            requested_count=1,
            found_count=1,
            scored_count=0,
            unchanged_count=0,
            skipped_rejected_count=0,
            skipped_superseded_count=0,
            invalid_evidence_count=0,
            minimum_rule_failed_count=0,
            failed_count=1,
            stopped_early=False,
            errors=[
                ConfidenceErrorRecord(
                    error_code="confidence_persistence_failed",
                    message="The synthetic score could not be persisted.",
                    request_id=str(request.request_id),
                    insight_id=insight_id,
                    recoverable=True,
                )
            ],
        )

    monkeypatch.setattr(analysis_service, "calculate_confidence", fail_confidence)
    async for client in make_client(tmp_path, provider_factory=provider_factory):
        conversation_id = await import_conversation(client)
        response = await client.post(
            "/api/v1/analysis",
            json={"conversation_ids": [conversation_id]},
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["insights_created"] == 1
        assert body["confidence_scored_count"] == 0
        assert body["confidence_failed_count"] == 1
        assert body["errors"][0]["error_code"] == "confidence_persistence_failed"
        assert (await client.get(f"/api/v1/insights/{body['insight_ids'][0]}")).status_code == 200


async def test_public_route_surface_has_no_delete_or_analysis_provider_controls(
    tmp_path: Path,
) -> None:
    async for client in make_client(tmp_path):
        schema = (await client.get("/openapi.json")).json()
        assert "/api/v1/analysis" in schema["paths"]
        assert set(schema["paths"]["/api/v1/analysis"]) == {"post"}
        assert all("delete" not in operations for operations in schema["paths"].values())
        request_schema = schema["components"]["schemas"]["AnalysisRequest"]
        properties = set(request_schema["properties"])
        assert properties == {
            "conversation_ids",
            "remote_consent",
            "start_at",
            "end_at",
            "stop_on_window_error",
        }

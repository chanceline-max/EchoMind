"""Health endpoint contract and privacy tests."""

import json

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from echomind.api.v1.health import HealthResponse
from echomind.core.config import Settings


@pytest.mark.anyio
async def test_health_returns_versioned_schema(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    parsed = HealthResponse.model_validate(response.json())
    assert parsed.status == "ok"
    assert parsed.service == "echomind-api"
    assert parsed.version == "0.1.0-test"


@pytest.mark.anyio
async def test_health_response_contains_only_public_fields(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert set(response.json()) == {"status", "service", "version"}
    assert response.headers["cache-control"] == "no-store"
    serialized = json.dumps(response.json()).lower()
    assert "frontend_origins" not in serialized
    assert "environment" not in serialized
    assert "secret" not in serialized
    assert "key" not in serialized


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)
@pytest.mark.anyio
async def test_cors_allows_configured_local_origins(client: AsyncClient, origin: str) -> None:
    response = await client.get("/api/v1/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.anyio
async def test_cors_does_not_allow_unknown_origin(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health",
        headers={"Origin": "https://untrusted.example"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_settings_reject_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="must not contain wildcards"):
        Settings(frontend_origins=["*"])

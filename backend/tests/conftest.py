"""Shared backend test fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from echomind.core.config import Settings
from echomind.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_name="EchoMind API Test",
        app_version="0.1.0-test",
        api_v1_prefix="/api/v1",
        environment="test",
        frontend_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client

"""Shared backend test fixtures."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from echomind.core.config import Settings
from echomind.db.base import Base
from echomind.db.session import create_db_engine, create_session_factory
from echomind.main import create_app
from echomind.models import Conversation  # noqa: F401 - registers all model tables


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    return Settings(
        app_name="EchoMind API Test",
        app_version="0.1.0-test",
        api_v1_prefix="/api/v1",
        environment="test",
        frontend_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        database_url=f"sqlite:///{(tmp_path / 'api-test.db').as_posix()}",
        import_temp_root=str(upload_root),
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client
    finally:
        app.state.engine.dispose()


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """Create an isolated SQLite database with enforced foreign keys."""

    database_path = tmp_path / "echomind-test.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

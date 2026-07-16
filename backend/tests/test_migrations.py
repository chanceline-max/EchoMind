"""Alembic lifecycle tests against a fresh temporary SQLite database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

CORE_TABLES = {
    "source_files",
    "conversations",
    "participants",
    "conversation_participants",
    "messages",
    "evidence",
    "insights",
    "insight_evidence",
    "profile_snapshots",
}


def alembic_config(database_path: Path) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_upgrade_downgrade_upgrade_lifecycle(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-lifecycle.db"
    config = alembic_config(database_path)

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        database_inspector = inspect(engine)
        assert CORE_TABLES <= set(database_inspector.get_table_names())
        file_hash_unique = database_inspector.get_unique_constraints("source_files")
        assert any(item["name"] == "uq_source_files_file_hash" for item in file_hash_unique)
        message_indexes = database_inspector.get_indexes("messages")
        assert any(item["name"] == "ix_messages_timestamp" for item in message_indexes)
        insight_indexes = {item["name"] for item in database_inspector.get_indexes("insights")}
        assert {
            "ix_insights_confidence",
            "ix_insights_insight_type",
            "ix_insights_status",
        } <= insight_indexes
        snapshot_indexes = database_inspector.get_indexes("profile_snapshots")
        assert any(item["name"] == "ix_profile_snapshots_generated_at" for item in snapshot_indexes)

        for table_name in CORE_TABLES:
            for foreign_key in database_inspector.get_foreign_keys(table_name):
                assert foreign_key["options"].get("ondelete") == "RESTRICT"
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert CORE_TABLES.isdisjoint(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert revision == "20260716_0001"
        assert CORE_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.check(config)

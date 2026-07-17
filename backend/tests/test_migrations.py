"""Alembic lifecycle tests against a fresh temporary SQLite database."""

from collections.abc import Iterator
from pathlib import Path

import pytest
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


@pytest.fixture
def migration_database_path(tmp_path: Path) -> Iterator[Path]:
    database_path = tmp_path / "migration-lifecycle.db"
    try:
        yield database_path
    finally:
        database_path.unlink(missing_ok=True)
        assert not database_path.exists()


def test_upgrade_downgrade_upgrade_lifecycle(migration_database_path: Path) -> None:
    database_path = migration_database_path
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
        assert any(
            item["name"] == "ix_messages_conversation_source_order" for item in message_indexes
        )
        message_columns = {item["name"] for item in database_inspector.get_columns("messages")}
        assert {
            "source_order",
            "source_location",
            "duplicate_of_message_id",
            "is_system_message",
            "is_recalled_message",
            "exclusion_reasons_json",
            "cleaning_operations_json",
        } <= message_columns
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
        assert revision == "20260717_0002"
        assert CORE_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.check(config)


def test_stage_five_upgrade_preserves_existing_stage_two_message(
    migration_database_path: Path,
) -> None:
    database_path = migration_database_path
    config = alembic_config(database_path)
    command.upgrade(config, "20260716_0001")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    source_id = "00000000-0000-0000-0000-000000000001"
    participant_id = "00000000-0000-0000-0000-000000000002"
    conversation_id = "00000000-0000-0000-0000-000000000003"
    message_id = "00000000-0000-0000-0000-000000000004"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source_files VALUES "
                "(:id, 'synthetic.json', 'json', :hash, NULL, 1, :now, "
                "'generic-json', '1.0', 'ready', NULL, '{}')"
            ),
            {"id": source_id, "hash": "a" * 64, "now": "2026-07-17 00:00:00"},
        )
        connection.execute(
            text("INSERT INTO participants VALUES (:id, 'Person A', '[]', 1, :now, '{}')"),
            {"id": participant_id, "now": "2026-07-17 00:00:00"},
        )
        connection.execute(
            text(
                "INSERT INTO conversations VALUES "
                "(:id, :source, 'generic', 'conversation-1', 'Synthetic', "
                "NULL, NULL, NULL, '{}')"
            ),
            {"id": conversation_id, "source": source_id},
        )
        connection.execute(
            text("INSERT INTO conversation_participants VALUES (:conversation, :person)"),
            {"conversation": conversation_id, "person": participant_id},
        )
        connection.execute(
            text(
                "INSERT INTO messages VALUES "
                "(:id, :conversation, 'message-1', :person, :now, 0, 'text', "
                "'untouched raw', 'untouched raw', NULL, 0, NULL, 0, NULL, "
                "'raw-v1', '{}', :now)"
            ),
            {
                "id": message_id,
                "conversation": conversation_id,
                "person": participant_id,
                "now": "2026-07-17 00:00:00",
            },
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT raw_content, normalized_content, source_order, "
                "duplicate_of_message_id FROM messages WHERE id = :id"
            ),
            {"id": message_id},
        ).one()
    engine.dispose()
    assert tuple(row) == ("untouched raw", "untouched raw", 0, None)

    command.downgrade(config, "20260716_0001")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT raw_content FROM messages WHERE id = :id"),
                {"id": message_id},
            ).scalar_one()
            == "untouched raw"
        )
    engine.dispose()
    command.upgrade(config, "head")

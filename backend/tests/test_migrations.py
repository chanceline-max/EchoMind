"""Alembic lifecycle tests against a fresh temporary SQLite database."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

CORE_TABLES = {
    "source_files",
    "conversations",
    "participants",
    "conversation_participants",
    "messages",
    "evidence",
    "insights",
    "insight_evidence",
    "insight_revisions",
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
            "ix_insights_confidence_input_fingerprint",
            "ix_insights_insight_type",
            "ix_insights_status",
            "ux_insights_insight_fingerprint",
        } <= insight_indexes
        evidence_indexes = {item["name"] for item in database_inspector.get_indexes("evidence")}
        assert "ux_evidence_evidence_fingerprint" in evidence_indexes
        insight_columns = {
            item["name"]: item for item in database_inspector.get_columns("insights")
        }
        assert {
            "insight_fingerprint",
            "model_confidence",
            "provider_name",
            "provider_request_id",
            "confidence_version",
            "explicit_self_report",
            "confidence_input_fingerprint",
            "confidence_factors_json",
            "confidence_explanation",
            "confidence_as_of",
            "confidence_calculated_at",
            "revision_number",
            "superseded_by_insight_id",
            "review_note",
            "reviewed_at",
        } <= insight_columns.keys()
        assert insight_columns["confidence_version"]["nullable"] is False
        evidence_columns = {item["name"] for item in database_inspector.get_columns("evidence")}
        assert {"evidence_fingerprint", "invalidation_reasons_json"} <= evidence_columns
        assert any(
            item["name"] == "ix_insight_revisions_insight_id"
            for item in database_inspector.get_indexes("insight_revisions")
        )
        snapshot_indexes = database_inspector.get_indexes("profile_snapshots")
        assert any(item["name"] == "ix_profile_snapshots_generated_at" for item in snapshot_indexes)
        assert any(
            item["name"] == "ix_profile_snapshots_generation_fingerprint" and item["unique"]
            for item in snapshot_indexes
        )
        snapshot_columns = {
            item["name"] for item in database_inspector.get_columns("profile_snapshots")
        }
        assert {
            "source_fingerprint",
            "generation_fingerprint",
            "document_hash",
            "generation_options_json",
            "source_manifest_json",
            "insight_count",
            "evidence_count",
            "source_status_at_generation",
        } <= snapshot_columns

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
        assert revision == "20260721_0006"
        assert CORE_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.check(config)


def test_stage_ten_upgrade_preserves_existing_profile_snapshot(
    migration_database_path: Path,
) -> None:
    config = alembic_config(migration_database_path)
    command.upgrade(config, "20260720_0005")
    engine = create_engine(f"sqlite:///{migration_database_path.as_posix()}")
    profile_id = "00000000-0000-0000-0000-000000000099"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO profile_snapshots "
                "(id, generated_at, profile_version, schema_version, markdown_content, "
                "json_content, source_range_start, source_range_end, statistics, limitations, "
                "evidence_state, invalidated_at, metadata) VALUES "
                "(:id, :generated, 'legacy-profile', 'legacy-schema', '# Legacy', '{}', "
                "NULL, NULL, '{}', '[]', 'valid', NULL, '{}')"
            ),
            {"id": profile_id, "generated": "2026-07-20 00:00:00"},
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{migration_database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT markdown_content, source_fingerprint, generation_fingerprint "
                    "FROM profile_snapshots WHERE id = :id"
                ),
                {"id": profile_id},
            ).one()
        assert row.markdown_content == "# Legacy"
        assert row.source_fingerprint is None
        assert row.generation_fingerprint is None
    finally:
        engine.dispose()

    command.downgrade(config, "20260720_0005")
    command.upgrade(config, "head")


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


def test_stage_seven_upgrade_preserves_existing_insight_and_evidence(
    migration_database_path: Path,
) -> None:
    database_path = migration_database_path
    config = alembic_config(database_path)
    command.upgrade(config, "20260717_0002")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    ids = {
        "source": "00000000-0000-4000-8000-000000000011",
        "participant": "00000000-0000-4000-8000-000000000012",
        "conversation": "00000000-0000-4000-8000-000000000013",
        "message": "00000000-0000-4000-8000-000000000014",
        "evidence": "00000000-0000-4000-8000-000000000015",
        "insight": "00000000-0000-4000-8000-000000000016",
        "now": "2026-07-18 00:00:00",
        "hash": "b" * 64,
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source_files "
                "(id, filename, file_type, file_hash, storage_path, byte_size, imported_at, "
                "parser_name, parser_version, status, archived_at, metadata) VALUES "
                "(:source, 'synthetic.json', 'json', :hash, NULL, 1, :now, "
                "'synthetic', '1.0', 'ready', NULL, '{}')"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO participants "
                "(id, canonical_name, aliases, is_profile_owner, created_at, metadata) "
                "VALUES (:participant, 'Synthetic Owner', '[]', 1, :now, '{}')"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO conversations "
                "(id, source_file_id, platform, source_conversation_id, title, started_at, "
                "ended_at, archived_at, metadata) VALUES "
                "(:conversation, :source, 'synthetic', 'c1', NULL, NULL, NULL, NULL, '{}')"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO conversation_participants (conversation_id, participant_id) "
                "VALUES (:conversation, :participant)"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO messages "
                "(id, conversation_id, source_message_id, sender_id, timestamp, sequence_index, "
                "message_type, raw_content, normalized_content, reply_to_message_id, is_deleted, "
                "archived_at, excluded_from_analysis, exclusion_reason, normalization_version, "
                "metadata, created_at, source_order, source_location, duplicate_of_message_id, "
                "is_system_message, is_recalled_message, exclusion_reasons_json, "
                "cleaning_operations_json) VALUES "
                "(:message, :conversation, 'm1', :participant, :now, 0, 'text', "
                "'old raw', 'old normalized', NULL, 0, NULL, 0, NULL, '1.0', '{}', :now, "
                "0, NULL, NULL, 0, 0, '[]', '[]')"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO evidence "
                "(id, message_id, excerpt, excerpt_start, excerpt_end, excerpt_hash, "
                "evidence_type, stance, relevance_score, is_valid, invalidated_at, "
                "invalidation_reason, created_at) VALUES "
                "(:evidence, :message, 'old normalized', 0, 14, :hash, 'supporting', "
                "'supports', 0.8, 1, NULL, NULL, :now)"
            ),
            ids,
        )
        connection.execute(
            text(
                "INSERT INTO insights "
                "(id, category, insight_type, title, statement, confidence, status, "
                "evidence_state, valid_from, valid_to, created_at, updated_at, model_name, "
                "extraction_version, reasoning_basis, alternative_explanations, metadata) "
                "VALUES (:insight, 'background', 'fact', 'Old title', 'Old statement', 0.5, "
                "'proposed', 'valid', NULL, NULL, :now, :now, NULL, 'old-v1', NULL, '[]', '{}')"
            ),
            ids,
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        insight = connection.execute(
            text(
                "SELECT statement, insight_fingerprint, model_confidence, confidence_version "
                "FROM insights WHERE id = :insight"
            ),
            ids,
        ).one()
        evidence = connection.execute(
            text("SELECT excerpt, evidence_fingerprint FROM evidence WHERE id = :evidence"),
            ids,
        ).one()
    engine.dispose()
    assert tuple(insight) == ("Old statement", None, None, "unscored")
    assert tuple(evidence) == ("old normalized", None)

    command.downgrade(config, "20260717_0002")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT statement FROM insights WHERE id = :insight"), ids
            ).scalar_one()
            == "Old statement"
        )
        assert (
            connection.execute(
                text("SELECT excerpt FROM evidence WHERE id = :evidence"), ids
            ).scalar_one()
            == "old normalized"
        )
    engine.dispose()
    command.upgrade(config, "head")


def test_stage_seven_unique_null_and_confidence_constraints(
    migration_database_path: Path,
) -> None:
    database_path = migration_database_path
    config = alembic_config(database_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    base = {
        "now": "2026-07-18 00:00:00",
        "fingerprint": "f" * 64,
    }
    statement = text(
        "INSERT INTO insights "
        "(id, category, insight_type, title, statement, confidence, status, evidence_state, "
        "valid_from, valid_to, created_at, updated_at, model_name, extraction_version, "
        "reasoning_basis, alternative_explanations, metadata, provider_name, "
        "provider_request_id, insight_fingerprint, model_confidence, confidence_version) "
        "VALUES (:id, 'other', 'fact', 'Title', :statement, 0, 'proposed', 'valid', NULL, "
        "NULL, :now, :now, NULL, 'candidate-extraction-1.0', NULL, '[]', '{}', NULL, "
        "NULL, :fingerprint, :model_confidence, 'unscored')"
    )
    with engine.begin() as connection:
        for index in range(2):
            connection.execute(
                statement,
                {
                    **base,
                    "id": f"00000000-0000-4000-8000-00000000002{index}",
                    "statement": f"Null fingerprint {index}",
                    "fingerprint": None,
                    "model_confidence": None,
                },
            )
        connection.execute(
            statement,
            {
                **base,
                "id": "00000000-0000-4000-8000-000000000030",
                "statement": "Unique fingerprint",
                "model_confidence": 0.5,
            },
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                statement,
                {
                    **base,
                    "id": "00000000-0000-4000-8000-000000000031",
                    "statement": "Duplicate fingerprint",
                    "model_confidence": 0.4,
                },
            )
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                statement,
                {
                    **base,
                    "id": "00000000-0000-4000-8000-000000000032",
                    "statement": "Invalid model confidence",
                    "fingerprint": "e" * 64,
                    "model_confidence": 1.1,
                },
            )
    engine.dispose()


def test_stage_eight_upgrade_preserves_unscored_insight_and_round_trips(
    migration_database_path: Path,
) -> None:
    database_path = migration_database_path
    config = alembic_config(database_path)
    command.upgrade(config, "20260718_0003")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    insight_id = "00000000-0000-4000-8000-000000000081"
    now = "2026-07-19 00:00:00"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO insights "
                "(id, category, insight_type, title, statement, confidence, status, "
                "evidence_state, valid_from, valid_to, created_at, updated_at, model_name, "
                "extraction_version, reasoning_basis, alternative_explanations, metadata, "
                "provider_name, provider_request_id, insight_fingerprint, model_confidence, "
                "confidence_version) VALUES "
                "(:id, 'background', 'fact', 'Old title', 'Old statement', 0, 'proposed', "
                "'invalid', NULL, NULL, :now, :now, NULL, 'old-v1', NULL, '[]', '{}', "
                "NULL, NULL, NULL, NULL, 'unscored')"
            ),
            {"id": insight_id, "now": now},
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT statement, confidence, confidence_version, explicit_self_report, "
                "confidence_input_fingerprint FROM insights WHERE id=:id"
            ),
            {"id": insight_id},
        ).one()
    engine.dispose()
    assert tuple(row) == ("Old statement", 0.0, "unscored", 0, None)

    command.downgrade(config, "20260718_0003")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    assert "explicit_self_report" not in {
        item["name"] for item in inspect(engine).get_columns("insights")
    }
    engine.dispose()
    command.upgrade(config, "head")


def test_stage_nine_upgrade_preserves_insight_and_revision_constraints(
    migration_database_path: Path,
) -> None:
    database_path = migration_database_path
    config = alembic_config(database_path)
    command.upgrade(config, "20260719_0004")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    insight_id = "00000000-0000-4000-8000-000000000091"
    replacement_id = "00000000-0000-4000-8000-000000000092"
    revision_id = "00000000-0000-4000-8000-000000000093"
    now = "2026-07-20 00:00:00"
    statement = text(
        "INSERT INTO insights "
        "(id, category, insight_type, title, statement, confidence, status, "
        "evidence_state, created_at, updated_at, extraction_version, "
        "alternative_explanations, metadata, confidence_version, explicit_self_report) "
        "VALUES (:id, 'background', 'fact', :title, :statement, 0, 'proposed', "
        "'valid', :now, :now, 'candidate-extraction-1.0', '[]', '{}', 'unscored', 1)"
    )
    with engine.begin() as connection:
        connection.execute(
            statement,
            {
                "id": insight_id,
                "title": "Synthetic old title",
                "statement": "Synthetic old statement.",
                "now": now,
            },
        )
        connection.execute(
            statement,
            {
                "id": replacement_id,
                "title": "Synthetic replacement",
                "statement": "Synthetic replacement statement.",
                "now": now,
            },
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        preserved = connection.execute(
            text(
                "SELECT statement, revision_number, review_note, "
                "superseded_by_insight_id FROM insights WHERE id=:id"
            ),
            {"id": insight_id},
        ).one()
        assert tuple(preserved) == ("Synthetic old statement.", 0, None, None)
        connection.execute(
            text(
                "INSERT INTO insight_revisions "
                "(id, insight_id, revision_number, action, actor_type, created_at, "
                "expected_previous_revision, changed_fields_json, snapshot_json, note) "
                "VALUES (:revision, :insight, 1, 'confirmed', 'local_user', :now, "
                "0, '{}', '{}', NULL)"
            ),
            {"revision": revision_id, "insight": insight_id, "now": now},
        )
        connection.execute(
            text(
                "UPDATE insights SET revision_number=1, status='superseded', "
                "superseded_by_insight_id=:replacement WHERE id=:insight"
            ),
            {"replacement": replacement_id, "insight": insight_id},
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE insights SET superseded_by_insight_id=:insight WHERE id=:insight"),
                {"insight": insight_id},
            )
    engine.dispose()

    command.downgrade(config, "20260719_0004")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        inspector = inspect(engine)
        assert "insight_revisions" not in inspector.get_table_names()
        assert "revision_number" not in {item["name"] for item in inspector.get_columns("insights")}
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT statement FROM insights WHERE id=:id"),
                    {"id": insight_id},
                ).scalar_one()
                == "Synthetic old statement."
            )
    finally:
        engine.dispose()
    command.upgrade(config, "head")

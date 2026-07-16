"""Create the minimal stage-two evidence-chain data model.

Revision ID: 20260716_0001
Revises: None
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.String(length=36)
UTC_DATETIME = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "source_files",
        sa.Column("id", UUID, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "file_type",
            sa.Enum(
                "json",
                "csv",
                "text",
                "weflow",
                "unknown",
                name="file_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("imported_at", UTC_DATETIME, nullable=False),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "ready",
                "failed",
                "archived",
                name="source_file_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("archived_at", UTC_DATETIME, nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint("byte_size >= 0", name="ck_source_files_byte_size_non_negative"),
        sa.CheckConstraint(
            "length(file_hash) = 64",
            name="ck_source_files_file_hash_sha256_length",
        ),
        sa.CheckConstraint(
            "length(trim(filename)) > 0",
            name="ck_source_files_filename_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(parser_name)) > 0",
            name="ck_source_files_parser_name_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(parser_version)) > 0",
            name="ck_source_files_parser_version_not_empty",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_files"),
        sa.UniqueConstraint("file_hash", name="uq_source_files_file_hash"),
    )
    op.create_table(
        "participants",
        sa.Column("id", UUID, nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("is_profile_owner", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTC_DATETIME, nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "length(trim(canonical_name)) > 0",
            name="ck_participants_canonical_name_not_empty",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_participants"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", UUID, nullable=False),
        sa.Column("source_file_id", UUID, nullable=False),
        sa.Column("platform", sa.String(length=100), nullable=False),
        sa.Column("source_conversation_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("started_at", UTC_DATETIME, nullable=True),
        sa.Column("ended_at", UTC_DATETIME, nullable=True),
        sa.Column("archived_at", UTC_DATETIME, nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "length(trim(platform)) > 0",
            name="ck_conversations_platform_not_empty",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_conversations_time_range_valid",
        ),
        sa.ForeignKeyConstraint(
            ["source_file_id"],
            ["source_files.id"],
            name="fk_conversations_source_file_id_source_files",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        sa.UniqueConstraint(
            "source_file_id",
            "source_conversation_id",
            name="uq_conversations_source_identity",
        ),
    )
    op.create_index(
        "ix_conversations_source_file_id",
        "conversations",
        ["source_file_id"],
        unique=False,
    )
    op.create_table(
        "conversation_participants",
        sa.Column("conversation_id", UUID, nullable=False),
        sa.Column("participant_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_conversation_participants_conversation_id_conversations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["participants.id"],
            name="fk_conversation_participants_participant_id_participants",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id",
            "participant_id",
            name="pk_conversation_participants",
        ),
    )
    op.create_table(
        "messages",
        sa.Column("id", UUID, nullable=False),
        sa.Column("conversation_id", UUID, nullable=False),
        sa.Column("source_message_id", sa.String(length=255), nullable=False),
        sa.Column("sender_id", UUID, nullable=False),
        sa.Column("timestamp", UTC_DATETIME, nullable=True),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column(
            "message_type",
            sa.Enum(
                "text",
                "image",
                "file",
                "system",
                "recalled",
                "unknown",
                name="message_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column("reply_to_message_id", UUID, nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("archived_at", UTC_DATETIME, nullable=True),
        sa.Column("excluded_from_analysis", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=500), nullable=True),
        sa.Column("normalization_version", sa.String(length=100), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", UTC_DATETIME, nullable=False),
        sa.CheckConstraint(
            "length(trim(normalization_version)) > 0",
            name="ck_messages_normalization_version_not_empty",
        ),
        sa.CheckConstraint(
            "sequence_index >= 0",
            name="ck_messages_sequence_index_non_negative",
        ),
        sa.CheckConstraint(
            "length(trim(source_message_id)) > 0",
            name="ck_messages_source_id_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_messages_conversation_id_conversations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id"],
            ["messages.id"],
            name="fk_messages_reply_to_message_id_messages",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["participants.id"],
            name="fk_messages_sender_id_participants",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint(
            "conversation_id",
            "source_message_id",
            name="uq_messages_conversation_source_id",
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index(
        "ix_messages_reply_to_message_id",
        "messages",
        ["reply_to_message_id"],
        unique=False,
    )
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"], unique=False)
    op.create_index("ix_messages_timestamp", "messages", ["timestamp"], unique=False)
    op.create_table(
        "evidence",
        sa.Column("id", UUID, nullable=False),
        sa.Column("message_id", UUID, nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("excerpt_start", sa.Integer(), nullable=False),
        sa.Column("excerpt_end", sa.Integer(), nullable=False),
        sa.Column("excerpt_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column(
            "stance",
            sa.Enum(
                "supports",
                "contradicts",
                "context",
                name="evidence_stance",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("invalidated_at", UTC_DATETIME, nullable=True),
        sa.Column("invalidation_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", UTC_DATETIME, nullable=False),
        sa.CheckConstraint(
            "length(trim(evidence_type)) > 0",
            name="ck_evidence_evidence_type_not_empty",
        ),
        sa.CheckConstraint(
            "length(excerpt) > 0",
            name="ck_evidence_excerpt_not_empty",
        ),
        sa.CheckConstraint(
            "length(excerpt_hash) = 64",
            name="ck_evidence_excerpt_hash_sha256_length",
        ),
        sa.CheckConstraint(
            "excerpt_end > excerpt_start",
            name="ck_evidence_excerpt_range_valid",
        ),
        sa.CheckConstraint(
            "excerpt_start >= 0",
            name="ck_evidence_excerpt_start_non_negative",
        ),
        sa.CheckConstraint(
            "is_valid = 1 OR invalidated_at IS NOT NULL",
            name="ck_evidence_invalid_evidence_has_timestamp",
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_evidence_relevance_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="fk_evidence_message_id_messages",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evidence"),
    )
    op.create_index("ix_evidence_message_id", "evidence", ["message_id"], unique=False)
    op.create_table(
        "insights",
        sa.Column("id", UUID, nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column(
            "insight_type",
            sa.Enum(
                "fact",
                "preference",
                "pattern",
                "inference",
                "hypothesis",
                "contradiction",
                "change",
                name="insight_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "proposed",
                "confirmed",
                "rejected",
                "superseded",
                name="insight_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "evidence_state",
            sa.Enum(
                "valid",
                "partial",
                "invalid",
                name="evidence_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("valid_from", UTC_DATETIME, nullable=True),
        sa.Column("valid_to", UTC_DATETIME, nullable=True),
        sa.Column("created_at", UTC_DATETIME, nullable=False),
        sa.Column("updated_at", UTC_DATETIME, nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("extraction_version", sa.String(length=100), nullable=False),
        sa.Column("reasoning_basis", sa.Text(), nullable=True),
        sa.Column("alternative_explanations", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "length(trim(category)) > 0",
            name="ck_insights_category_not_empty",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_insights_confidence_range",
        ),
        sa.CheckConstraint(
            "length(trim(extraction_version)) > 0",
            name="ck_insights_extraction_version_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(statement)) > 0",
            name="ck_insights_statement_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_insights_title_not_empty",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_insights_valid_time_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_insights"),
    )
    op.create_index("ix_insights_confidence", "insights", ["confidence"], unique=False)
    op.create_index("ix_insights_insight_type", "insights", ["insight_type"], unique=False)
    op.create_index("ix_insights_status", "insights", ["status"], unique=False)
    op.create_table(
        "insight_evidence",
        sa.Column("insight_id", UUID, nullable=False),
        sa.Column("evidence_id", UUID, nullable=False),
        sa.Column("created_at", UTC_DATETIME, nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
            name="fk_insight_evidence_evidence_id_evidence",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["insight_id"],
            ["insights.id"],
            name="fk_insight_evidence_insight_id_insights",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("insight_id", "evidence_id", name="pk_insight_evidence"),
    )
    op.create_table(
        "profile_snapshots",
        sa.Column("id", UUID, nullable=False),
        sa.Column("generated_at", UTC_DATETIME, nullable=False),
        sa.Column("profile_version", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("markdown_content", sa.Text(), nullable=False),
        sa.Column("json_content", sa.JSON(), nullable=False),
        sa.Column("source_range_start", UTC_DATETIME, nullable=True),
        sa.Column("source_range_end", UTC_DATETIME, nullable=True),
        sa.Column("statistics", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column(
            "evidence_state",
            sa.Enum(
                "valid",
                "partial",
                "invalid",
                name="profile_evidence_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("invalidated_at", UTC_DATETIME, nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "evidence_state != 'invalid' OR invalidated_at IS NOT NULL",
            name="ck_profile_snapshots_invalid_profile_has_timestamp",
        ),
        sa.CheckConstraint(
            "length(trim(profile_version)) > 0",
            name="ck_profile_snapshots_profile_version_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(schema_version)) > 0",
            name="ck_profile_snapshots_schema_version_not_empty",
        ),
        sa.CheckConstraint(
            "source_range_end IS NULL OR source_range_start IS NULL "
            "OR source_range_end >= source_range_start",
            name="ck_profile_snapshots_source_range_valid",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profile_snapshots"),
    )
    op.create_index(
        "ix_profile_snapshots_generated_at",
        "profile_snapshots",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_profile_snapshots_generated_at", table_name="profile_snapshots")
    op.drop_table("profile_snapshots")
    op.drop_table("insight_evidence")
    op.drop_index("ix_insights_status", table_name="insights")
    op.drop_index("ix_insights_insight_type", table_name="insights")
    op.drop_index("ix_insights_confidence", table_name="insights")
    op.drop_table("insights")
    op.drop_index("ix_evidence_message_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_messages_timestamp", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_reply_to_message_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversation_participants")
    op.drop_index("ix_conversations_source_file_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("participants")
    op.drop_table("source_files")

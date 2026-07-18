"""Extend immutable Profile snapshots with deterministic provenance.

Revision ID: 20260721_0006
Revises: 20260720_0005
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0006"
down_revision: str | None = "20260720_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("profile_snapshots", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("source_fingerprint", sa.String(length=64)))
        batch_op.add_column(sa.Column("generation_fingerprint", sa.String(length=64)))
        batch_op.add_column(sa.Column("document_hash", sa.String(length=64)))
        batch_op.add_column(sa.Column("generation_options_json", sa.JSON()))
        batch_op.add_column(sa.Column("source_manifest_json", sa.JSON()))
        batch_op.add_column(sa.Column("insight_count", sa.Integer()))
        batch_op.add_column(sa.Column("evidence_count", sa.Integer()))
        batch_op.add_column(sa.Column("source_status_at_generation", sa.String(length=32)))
        batch_op.create_check_constraint(
            "source_fingerprint_sha256_length",
            "source_fingerprint IS NULL OR length(source_fingerprint) = 64",
        )
        batch_op.create_check_constraint(
            "generation_fingerprint_sha256_length",
            "generation_fingerprint IS NULL OR length(generation_fingerprint) = 64",
        )
        batch_op.create_check_constraint(
            "document_hash_sha256_length",
            "document_hash IS NULL OR length(document_hash) = 64",
        )
        batch_op.create_check_constraint(
            "insight_count_non_negative", "insight_count IS NULL OR insight_count >= 0"
        )
        batch_op.create_check_constraint(
            "evidence_count_non_negative", "evidence_count IS NULL OR evidence_count >= 0"
        )
        batch_op.create_check_constraint(
            "source_status_at_generation_current",
            "source_status_at_generation IS NULL OR source_status_at_generation = 'current'",
        )
        batch_op.create_index(
            "ix_profile_snapshots_generation_fingerprint",
            ["generation_fingerprint"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("profile_snapshots", recreate="always") as batch_op:
        batch_op.drop_index("ix_profile_snapshots_generation_fingerprint")
        batch_op.drop_constraint("source_status_at_generation_current", type_="check")
        batch_op.drop_constraint("evidence_count_non_negative", type_="check")
        batch_op.drop_constraint("insight_count_non_negative", type_="check")
        batch_op.drop_constraint("document_hash_sha256_length", type_="check")
        batch_op.drop_constraint("generation_fingerprint_sha256_length", type_="check")
        batch_op.drop_constraint("source_fingerprint_sha256_length", type_="check")
        batch_op.drop_column("source_status_at_generation")
        batch_op.drop_column("evidence_count")
        batch_op.drop_column("insight_count")
        batch_op.drop_column("source_manifest_json")
        batch_op.drop_column("generation_options_json")
        batch_op.drop_column("document_hash")
        batch_op.drop_column("generation_fingerprint")
        batch_op.drop_column("source_fingerprint")

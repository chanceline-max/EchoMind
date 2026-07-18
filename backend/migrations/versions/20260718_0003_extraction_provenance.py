"""Add exact extraction provenance and idempotency fields.

Revision ID: 20260718_0003
Revises: 20260717_0002
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0003"
down_revision: str | None = "20260717_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("insights", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("provider_name", sa.String(length=128), nullable=True))
        batch_op.add_column(
            sa.Column("provider_request_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("insight_fingerprint", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("model_confidence", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "confidence_version",
                sa.String(length=100),
                nullable=False,
                server_default="unscored",
            )
        )
        batch_op.create_check_constraint(
            "model_confidence_range",
            "model_confidence IS NULL OR "
            "(model_confidence >= 0 AND model_confidence <= 1)",
        )
        batch_op.create_check_constraint(
            "confidence_version_not_empty",
            "length(trim(confidence_version)) > 0",
        )
        batch_op.create_check_constraint(
            "insight_fingerprint_sha256_length",
            "insight_fingerprint IS NULL OR length(insight_fingerprint) = 64",
        )
        batch_op.create_index(
            "ux_insights_insight_fingerprint",
            ["insight_fingerprint"],
            unique=True,
        )
    with op.batch_alter_table("evidence", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("evidence_fingerprint", sa.String(length=64), nullable=True)
        )
        batch_op.create_check_constraint(
            "evidence_fingerprint_sha256_length",
            "evidence_fingerprint IS NULL OR length(evidence_fingerprint) = 64",
        )
        batch_op.create_index(
            "ux_evidence_evidence_fingerprint",
            ["evidence_fingerprint"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence", recreate="always") as batch_op:
        batch_op.drop_index("ux_evidence_evidence_fingerprint")
        batch_op.drop_constraint("evidence_fingerprint_sha256_length", type_="check")
        batch_op.drop_column("evidence_fingerprint")
    with op.batch_alter_table("insights", recreate="always") as batch_op:
        batch_op.drop_index("ux_insights_insight_fingerprint")
        batch_op.drop_constraint("insight_fingerprint_sha256_length", type_="check")
        batch_op.drop_constraint("confidence_version_not_empty", type_="check")
        batch_op.drop_constraint("model_confidence_range", type_="check")
        batch_op.drop_column("confidence_version")
        batch_op.drop_column("model_confidence")
        batch_op.drop_column("insight_fingerprint")
        batch_op.drop_column("provider_request_id")
        batch_op.drop_column("provider_name")

"""Add deterministic confidence scoring persistence fields.

Revision ID: 20260719_0004
Revises: 20260718_0003
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_0004"
down_revision: str | None = "20260718_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("insights", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "explicit_self_report",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("confidence_input_fingerprint", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("confidence_factors_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("confidence_explanation", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("confidence_as_of", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("confidence_calculated_at", sa.DateTime(), nullable=True))
        batch_op.create_check_constraint(
            "confidence_input_fingerprint_sha256_length",
            "confidence_input_fingerprint IS NULL OR length(confidence_input_fingerprint) = 64",
        )
        batch_op.create_check_constraint(
            "confidence_explanation_length",
            "confidence_explanation IS NULL OR length(confidence_explanation) <= 4000",
        )
        batch_op.create_index(
            "ix_insights_confidence_input_fingerprint",
            ["confidence_input_fingerprint"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("insights", recreate="always") as batch_op:
        batch_op.drop_index("ix_insights_confidence_input_fingerprint")
        batch_op.drop_constraint("confidence_explanation_length", type_="check")
        batch_op.drop_constraint("confidence_input_fingerprint_sha256_length", type_="check")
        batch_op.drop_column("confidence_calculated_at")
        batch_op.drop_column("confidence_as_of")
        batch_op.drop_column("confidence_explanation")
        batch_op.drop_column("confidence_factors_json")
        batch_op.drop_column("confidence_input_fingerprint")
        batch_op.drop_column("explicit_self_report")

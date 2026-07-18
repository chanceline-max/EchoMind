"""Add Insight review state, Evidence reasons, and append-only revisions.

Revision ID: 20260720_0005
Revises: 20260719_0004
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0005"
down_revision: str | None = "20260719_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("insights", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "revision_number",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("superseded_by_insight_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch_op.create_check_constraint(
            "revision_number_non_negative",
            "revision_number >= 0",
        )
        batch_op.create_check_constraint(
            "review_note_length",
            "review_note IS NULL OR length(review_note) <= 2000",
        )
        batch_op.create_check_constraint(
            "superseded_target_not_self",
            "superseded_by_insight_id IS NULL OR superseded_by_insight_id <> id",
        )
        batch_op.create_check_constraint(
            "superseded_status_target_consistent",
            "status = 'superseded' OR superseded_by_insight_id IS NULL",
        )
        batch_op.create_foreign_key(
            "fk_insights_superseded_by_insight_id",
            "insights",
            ["superseded_by_insight_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_insights_superseded_by_insight_id",
            ["superseded_by_insight_id"],
            unique=False,
        )

    with op.batch_alter_table("evidence", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "invalidation_reasons_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    op.execute(
        sa.text(
            "UPDATE evidence SET invalidation_reasons_json = :reasons WHERE is_valid = 0"
        ).bindparams(reasons='["other_system_reason"]')
    )

    op.create_table(
        "insight_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("insight_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "confirmed",
                "rejected",
                "restored_to_proposed",
                "restored_to_confirmed",
                "edited",
                "superseded",
                "evidence_invalidated",
                "evidence_revalidated",
                name="insight_revision_action",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "actor_type",
            sa.Enum(
                "local_user",
                "system",
                name="revision_actor_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expected_previous_revision", sa.Integer(), nullable=False),
        sa.Column("changed_fields_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("revision_number >= 1", name="revision_number_positive"),
        sa.CheckConstraint(
            "expected_previous_revision >= 0",
            name="expected_previous_revision_non_negative",
        ),
        sa.CheckConstraint("note IS NULL OR length(note) <= 2000", name="note_length"),
        sa.ForeignKeyConstraint(
            ["insight_id"],
            ["insights.id"],
            name="fk_insight_revisions_insight_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "insight_id",
            "revision_number",
            name="uq_insight_revisions_number",
        ),
    )
    op.create_index(
        "ix_insight_revisions_insight_id",
        "insight_revisions",
        ["insight_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_insight_revisions_insight_id", table_name="insight_revisions")
    op.drop_table("insight_revisions")

    with op.batch_alter_table("evidence", recreate="always") as batch_op:
        batch_op.drop_column("invalidation_reasons_json")

    with op.batch_alter_table("insights", recreate="always") as batch_op:
        batch_op.drop_index("ix_insights_superseded_by_insight_id")
        batch_op.drop_constraint("fk_insights_superseded_by_insight_id", type_="foreignkey")
        batch_op.drop_constraint("superseded_target_not_self", type_="check")
        batch_op.drop_constraint("superseded_status_target_consistent", type_="check")
        batch_op.drop_constraint("review_note_length", type_="check")
        batch_op.drop_constraint("revision_number_non_negative", type_="check")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("review_note")
        batch_op.drop_column("superseded_by_insight_id")
        batch_op.drop_column("revision_number")

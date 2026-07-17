"""Add lossless stage-five message persistence fields.

Revision ID: 20260717_0002
Revises: 20260716_0001
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = sa.String(length=36)


def upgrade() -> None:
    with op.batch_alter_table("messages", recreate="always") as batch_op:
        batch_op.alter_column(
            "message_type",
            existing_type=sa.Enum(
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
            type_=sa.Enum(
                "text",
                "image",
                "file",
                "audio",
                "video",
                "system",
                "recalled",
                "other",
                "unknown",
                name="message_type",
                native_enum=False,
                create_constraint=True,
            ),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column("source_order", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("source_location", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("duplicate_of_message_id", UUID, nullable=True))
        batch_op.add_column(
            sa.Column("is_system_message", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column(
                "is_recalled_message", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(
            sa.Column("exclusion_reasons_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("cleaning_operations_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.create_check_constraint("source_order_non_negative", "source_order >= 0")
        batch_op.create_foreign_key(
            "fk_messages_duplicate_of_message_id_messages",
            "messages",
            ["duplicate_of_message_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_messages_duplicate_of_message_id",
            ["duplicate_of_message_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_messages_conversation_source_order",
            ["conversation_id", "source_order"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("messages", recreate="always") as batch_op:
        batch_op.drop_index("ix_messages_conversation_source_order")
        batch_op.drop_index("ix_messages_duplicate_of_message_id")
        batch_op.drop_constraint(
            "fk_messages_duplicate_of_message_id_messages",
            type_="foreignkey",
        )
        batch_op.drop_constraint("source_order_non_negative", type_="check")
        batch_op.drop_column("cleaning_operations_json")
        batch_op.drop_column("exclusion_reasons_json")
        batch_op.drop_column("is_recalled_message")
        batch_op.drop_column("is_system_message")
        batch_op.drop_column("duplicate_of_message_id")
        batch_op.drop_column("source_location")
        batch_op.drop_column("source_order")
        batch_op.alter_column(
            "message_type",
            existing_type=sa.Enum(
                "text",
                "image",
                "file",
                "audio",
                "video",
                "system",
                "recalled",
                "other",
                "unknown",
                name="message_type",
                native_enum=False,
                create_constraint=True,
            ),
            type_=sa.Enum(
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
            existing_nullable=False,
        )

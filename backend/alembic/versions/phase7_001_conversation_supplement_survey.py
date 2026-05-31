"""Conversation supplement survey + per-user survey library."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "phase7_001"
down_revision = "phase6_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_surveys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("template_version", sa.String(length=32), nullable=False, server_default="1"),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_conversation_surveys_conversation_id"),
        "conversation_surveys",
        ["conversation_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_conversation_surveys_user_id"),
        "conversation_surveys",
        ["user_id"],
        unique=False,
    )
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("conversation_surveys", "template_version", server_default=None)

    op.create_table(
        "user_survey_library",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("template_version", sa.String(length=32), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    if bind.dialect.name != "sqlite":
        op.alter_column("user_survey_library", "template_version", server_default=None)


def downgrade() -> None:
    op.drop_table("user_survey_library")
    op.drop_index(op.f("ix_conversation_surveys_user_id"), table_name="conversation_surveys")
    op.drop_index(op.f("ix_conversation_surveys_conversation_id"), table_name="conversation_surveys")
    op.drop_table("conversation_surveys")

"""Add conversations.rolling_summary for long-context chat."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "phase6_001"
down_revision = "phase5_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "rolling_summary",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "rolling_folded_message_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("conversations", "rolling_summary", server_default=None)
        op.alter_column(
            "conversations", "rolling_folded_message_count", server_default=None
        )


def downgrade() -> None:
    op.drop_column("conversations", "rolling_folded_message_count")
    op.drop_column("conversations", "rolling_summary")

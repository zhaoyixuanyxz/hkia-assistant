"""phase4: users.role for admin Bearer access"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "phase4_001"
down_revision = "phase3_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")

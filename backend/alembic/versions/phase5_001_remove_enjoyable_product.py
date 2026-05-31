"""Remove retired product clo-enjoyable-life-income-plan from catalog."""

from __future__ import annotations

from alembic import op

revision = "phase5_001"
down_revision = "phase4_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM product_sources WHERE product_id = 'clo-enjoyable-life-income-plan'"
    )
    op.execute("DELETE FROM products WHERE id = 'clo-enjoyable-life-income-plan'")


def downgrade() -> None:
    pass

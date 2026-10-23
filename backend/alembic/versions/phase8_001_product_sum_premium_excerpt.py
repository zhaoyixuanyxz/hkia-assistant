"""products: sum_assured, premium, excerpt_date"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "phase8_001"
down_revision = "phase7_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("sum_assured", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("premium", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("excerpt_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "excerpt_date")
    op.drop_column("products", "premium")
    op.drop_column("products", "sum_assured")

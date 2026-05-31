"""phase2: conversations governance + recommendation traces"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "phase2_001"
down_revision = "mvp_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())

    if "conversations" in tables:
        cols = {c["name"] for c in insp.get_columns("conversations")}
        if "is_pinned" not in cols:
            op.add_column(
                "conversations",
                sa.Column(
                    "is_pinned",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "pinned_at" not in cols:
            op.add_column(
                "conversations",
                sa.Column("pinned_at", sa.DateTime(), nullable=True),
            )
        if "deleted_at" not in cols:
            op.add_column(
                "conversations",
                sa.Column("deleted_at", sa.DateTime(), nullable=True),
            )

    if "product_recommendation_traces" not in tables:
        op.create_table(
            "product_recommendation_traces",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("report_id", sa.Integer(), nullable=True),
            sa.Column("query_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("candidates_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("final_choice_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("rationale_text", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
            sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())
    if "product_recommendation_traces" in tables:
        op.drop_table("product_recommendation_traces")
    if "conversations" in tables:
        cols = {c["name"] for c in insp.get_columns("conversations")}
        if "deleted_at" in cols:
            op.drop_column("conversations", "deleted_at")
        if "pinned_at" in cols:
            op.drop_column("conversations", "pinned_at")
        if "is_pinned" in cols:
            op.drop_column("conversations", "is_pinned")

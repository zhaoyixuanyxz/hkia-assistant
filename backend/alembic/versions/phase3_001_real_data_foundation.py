"""phase3: real products, market indicators, update jobs"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "phase3_001"
down_revision = "phase2_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("highlights", sa.Text(), nullable=False, server_default=""),
        sa.Column("coverage_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("clause_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("official_url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("source_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_review_status", "products", ["review_status"])

    op.create_table(
        "product_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("ref", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    op.create_index("ix_product_sources_product_id", "product_sources", ["product_id"])

    op.create_table(
        "market_indicators",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(length=1024), nullable=False, server_default=""),
        sa.Column("trend_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_market_indicators_name", "market_indicators", ["name"])

    op.create_table(
        "data_update_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("detail_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_data_update_jobs_job_type", "data_update_jobs", ["job_type"])
    op.create_index("ix_data_update_jobs_status", "data_update_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_data_update_jobs_status", table_name="data_update_jobs")
    op.drop_index("ix_data_update_jobs_job_type", table_name="data_update_jobs")
    op.drop_table("data_update_jobs")

    op.drop_index("ix_market_indicators_name", table_name="market_indicators")
    op.drop_table("market_indicators")

    op.drop_index("ix_product_sources_product_id", table_name="product_sources")
    op.drop_table("product_sources")

    op.drop_index("ix_products_review_status", table_name="products")
    op.drop_index("ix_products_category", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_table("products")

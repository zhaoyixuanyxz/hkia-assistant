from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app import db as db_mod
from app.models import Product
from app.retired_products import RETIRED_PRODUCT_IDS
from app.stub_data import load_product_stubs


def _product_summary(product: Product) -> str:
    parts = [
        product.highlights.strip(),
        product.coverage_summary.strip(),
        product.target_audience.strip(),
        product.clause_summary.strip(),
    ]
    merged = "；".join(p for p in parts if p)
    return merged[:2000]


def product_to_row(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "summary": _product_summary(product),
        "source_url": product.official_url,
        "is_sample": bool(product.is_sample),
        "updated_at": product.updated_at.isoformat() + "Z",
        "review_status": product.review_status,
        "sum_assured": product.sum_assured,
        "premium": product.premium,
        "excerpt_date": product.excerpt_date.isoformat() if product.excerpt_date else None,
    }


def load_active_product_rows() -> list[dict]:
    if db_mod.SessionLocal is None:
        return []
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        rows = s.scalars(
            select(Product)
            .where(Product.review_status == "active")
            .where(Product.id.not_in(sorted(RETIRED_PRODUCT_IDS)))
            .order_by(Product.updated_at.desc(), Product.id.asc())
        ).all()
        return [product_to_row(r) for r in rows]
    finally:
        s.close()


def load_retrievable_product_rows() -> list[dict]:
    rows = load_active_product_rows()
    if rows:
        return rows
    # Fallback for local dev/tests before phase3 seed import.
    return load_product_stubs()


def parse_iso_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

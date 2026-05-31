from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
load_dotenv(REPO_ROOT / ".env")

from app import db as db_mod  # noqa: E402
from app.embeddings import get_embedding_service  # noqa: E402
from app.models import Product, ProductSource  # noqa: E402
from app.retired_products import RETIRED_PRODUCT_IDS  # noqa: E402
from app.product_data import load_active_product_rows  # noqa: E402
from app.qdrant_store import (  # noqa: E402
    delete_product_vectors_by_external_ids,
    ensure_product_collection,
    get_qdrant_client,
    upsert_product_points,
)

REQUIRED_FIELDS = [
    "id",
    "name",
    "category",
    "highlights",
    "coverage_summary",
    "target_audience",
    "clause_summary",
    "official_url",
    "source_note",
]


def _valid_url(raw: str) -> bool:
    p = urlparse((raw or "").strip())
    return p.scheme in {"http", "https"} and bool(p.netloc)


def _load_rows(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("JSON must be an array of product objects.")
        return [dict(x) for x in data]
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]
    raise ValueError("Only .json or .csv imports are supported.")


def _normalize_row(raw: dict) -> dict:
    row = {k: str(raw.get(k, "")).strip() for k in REQUIRED_FIELDS}
    missing = [k for k in REQUIRED_FIELDS if not row.get(k)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    if not _valid_url(row["official_url"]):
        raise ValueError(f"Invalid official_url: {row['official_url']}")
    review_status = str(raw.get("review_status", "pending_review")).strip() or "pending_review"
    if review_status not in {"active", "pending_review", "obsolete"}:
        raise ValueError(f"Invalid review_status: {review_status}")
    is_sample = str(raw.get("is_sample", "false")).strip().lower() in {"1", "true", "yes", "y"}
    row["review_status"] = review_status
    row["is_sample"] = is_sample
    return row


def _upsert_products(rows: list[dict], source_kind: str, source_ref: str) -> int:
    if db_mod.SessionLocal is None:
        db_mod.init_engine()
    db_mod.create_tables()
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        count = 0
        for raw in rows:
            pid = str(raw.get("id", "")).strip()
            if pid in RETIRED_PRODUCT_IDS:
                continue
            row = _normalize_row(raw)
            existing = s.scalar(select(Product).where(Product.id == row["id"]))
            if existing is None:
                existing = Product(id=row["id"])
                s.add(existing)
            existing.name = row["name"]
            existing.category = row["category"]
            existing.highlights = row["highlights"]
            existing.coverage_summary = row["coverage_summary"]
            existing.target_audience = row["target_audience"]
            existing.clause_summary = row["clause_summary"]
            existing.official_url = row["official_url"]
            existing.source_note = row["source_note"]
            existing.review_status = row["review_status"]
            existing.is_sample = bool(row["is_sample"])
            s.add(
                ProductSource(
                    product_id=row["id"],
                    kind=source_kind,
                    ref=source_ref,
                    raw_json=raw,
                )
            )
            count += 1
        s.commit()
        return count
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _upsert_qdrant_for_active_products() -> None:
    if get_qdrant_client() is None:
        print("QDRANT_URL not set; skipped vector upsert.")
        return
    retired = sorted(RETIRED_PRODUCT_IDS)
    if retired:
        delete_product_vectors_by_external_ids(retired)
    rows = load_active_product_rows()
    if not rows:
        print("No active products found; skipped vector upsert.")
        return
    texts = [
        f"{r.get('name', '')} {r.get('summary', '')} {r.get('category', '')}"
        for r in rows
    ]
    emb = get_embedding_service()
    vectors = emb.embed_texts(texts)
    ensure_product_collection(len(vectors[0]))
    upsert_product_points(rows, vectors)
    print(f"Upserted {len(rows)} active products to Qdrant.")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python scripts/import_products.py <path/to/products.json|csv>"
        )
    src = Path(sys.argv[1]).resolve()
    if not src.exists():
        raise SystemExit(f"Input file not found: {src}")
    rows = _load_rows(src)
    imported = _upsert_products(rows, src.suffix.lower().lstrip("."), src.name)
    print(f"Imported {imported} rows into products/product_sources.")
    _upsert_qdrant_for_active_products()


if __name__ == "__main__":
    main()

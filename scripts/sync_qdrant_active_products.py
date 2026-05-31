"""Upsert vectors for all review_status=active products into Qdrant (uses DATABASE_URL + QDRANT_URL from env)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from app import db as db_mod  # noqa: E402
from app.embeddings import get_embedding_service  # noqa: E402
from app.product_data import load_active_product_rows  # noqa: E402
from app.qdrant_store import (  # noqa: E402
    delete_product_vectors_by_external_ids,
    ensure_product_collection,
    get_qdrant_client,
    upsert_product_points,
)
from app.retired_products import RETIRED_PRODUCT_IDS  # noqa: E402


def main() -> None:
    if get_qdrant_client() is None:
        print("QDRANT_URL not set; nothing to do.")
        return
    if db_mod.SessionLocal is None:
        db_mod.init_engine()
    db_mod.create_tables()
    retired = sorted(RETIRED_PRODUCT_IDS)
    if retired:
        delete_product_vectors_by_external_ids(retired)
        print(f"Removed retired product vectors from Qdrant: {retired}")
    rows = load_active_product_rows()
    if not rows:
        print("No active products in DB.")
        return
    texts = [f"{r.get('name', '')} {r.get('summary', '')} {r.get('category', '')}" for r in rows]
    emb = get_embedding_service()
    vectors = emb.embed_texts(texts)
    ensure_product_collection(len(vectors[0]))
    upsert_product_points(rows, vectors)
    print(f"Upserted {len(rows)} active products to Qdrant.")


if __name__ == "__main__":
    main()

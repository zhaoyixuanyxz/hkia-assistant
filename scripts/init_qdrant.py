"""Populate Qdrant `knowledge_products` from active DB products or demo stubs."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")


def main() -> None:
    from app import db as db_mod
    from app.embeddings import get_embedding_service
    from app.qdrant_store import (
        ensure_product_collection,
        get_qdrant_client,
        upsert_product_points,
    )
    from app.product_data import load_active_product_rows
    from app.stub_data import load_product_stubs

    if get_qdrant_client() is None:
        print("QDRANT_URL is not set; skip.")
        raise SystemExit(0)
    if db_mod.SessionLocal is None:
        db_mod.init_engine()
    db_mod.create_tables()
    stubs = load_active_product_rows() or load_product_stubs()
    texts = [
        f"{s.get('name','')} {s.get('summary','')} {s.get('category','')}" for s in stubs
    ]
    emb = get_embedding_service()
    vectors = emb.embed_texts(texts)
    ensure_product_collection(len(vectors[0]))
    upsert_product_points(stubs, vectors)
    print(f"Upserted {len(stubs)} product stubs into Qdrant.")


if __name__ == "__main__":
    main()

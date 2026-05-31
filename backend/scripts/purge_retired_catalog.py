"""Remove retired product IDs from Postgres + Qdrant (exact IDs only — see app.retired_products).

Run from repo:
  python backend/scripts/purge_retired_catalog.py

Docker Compose:
  docker compose exec backend python scripts/purge_retired_catalog.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ENV = BACKEND_ROOT.parent / ".env"
if _REPO_ENV.is_file():
    from dotenv import load_dotenv

    load_dotenv(_REPO_ENV)

sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete  # noqa: E402

from app import db as db_mod  # noqa: E402
from app.models import Product, ProductSource  # noqa: E402
from app.qdrant_store import delete_product_vectors_by_external_ids, get_qdrant_client  # noqa: E402
from app.retired_products import RETIRED_PRODUCT_IDS  # noqa: E402


def main() -> None:
    ids = sorted(RETIRED_PRODUCT_IDS)
    if not ids:
        print("RETIRED_PRODUCT_IDS is empty; nothing to purge.")
        return

    if db_mod.SessionLocal is None:
        db_mod.init_engine()
    db_mod.create_tables()

    with db_mod.SessionLocal() as session:  # type: ignore[misc]
        for pid in ids:
            session.execute(delete(ProductSource).where(ProductSource.product_id == pid))
            session.execute(delete(Product).where(Product.id == pid))
        session.commit()

    print(f"Postgres: deleted rows for product ids {ids} (product_sources then products).")

    if get_qdrant_client() is None:
        print("QDRANT_URL not set; skipped vector purge.")
        return

    delete_product_vectors_by_external_ids(list(ids))
    print(f"Qdrant: deleted vectors for external ids {ids}.")


if __name__ == "__main__":
    main()

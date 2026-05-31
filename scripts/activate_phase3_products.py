from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
load_dotenv(REPO_ROOT / ".env")

from app import db as db_mod  # noqa: E402
from app.models import Product  # noqa: E402
from app.retired_products import RETIRED_PRODUCT_IDS  # noqa: E402

SEED_FILES = [
    REPO_ROOT / "backend" / "app" / "data" / "phase3_products_seed.v1.json",
    REPO_ROOT / "backend" / "app" / "data" / "phase3_products_seed.v2.json",
    REPO_ROOT / "backend" / "app" / "data" / "phase3_products_seed.v3.json",
]


def _seed_product_ids() -> list[str]:
    seen: dict[str, None] = {}
    for path in SEED_FILES:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data:
            pid = str(row.get("id", "")).strip()
            if pid and pid not in RETIRED_PRODUCT_IDS:
                seen[pid] = None
    return list(seen.keys())


def main() -> None:
    ids = _seed_product_ids()
    if not ids:
        raise SystemExit("No product ids found in seed file.")

    if db_mod.SessionLocal is None:
        db_mod.init_engine()
    db_mod.create_tables()
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        rows = s.scalars(select(Product).where(Product.id.in_(ids)).order_by(Product.id.asc())).all()
        if not rows:
            raise SystemExit("No matching products found in DB. Import seed first.")

        print("Before:")
        for row in rows:
            print(f"- {row.id}: {row.review_status}")

        for row in rows:
            row.review_status = "active"
        s.commit()

        refreshed = s.scalars(select(Product).where(Product.id.in_(ids)).order_by(Product.id.asc())).all()
        print("After:")
        for row in refreshed:
            print(f"- {row.id}: {row.review_status}")
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


if __name__ == "__main__":
    main()

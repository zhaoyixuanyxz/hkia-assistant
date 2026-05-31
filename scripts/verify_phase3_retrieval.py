from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
load_dotenv(REPO_ROOT / ".env")

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.qdrant_store import get_qdrant_client  # noqa: E402

SEED_FILE = REPO_ROOT / "backend" / "app" / "data" / "phase3_products_seed.v1.json"


def _seed_ids() -> set[str]:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    return {str(item.get("id", "")).strip() for item in data if str(item.get("id", "")).strip()}


def main() -> None:
    expected_ids = _seed_ids()
    if not expected_ids:
        raise SystemExit("No seed product ids found.")

    client = TestClient(app)

    rk = client.get("/knowledge/products", params={"mode": "keyword", "q": "Income"})
    if rk.status_code != 200:
        raise SystemExit(f"Keyword search failed: {rk.status_code} {rk.text}")
    items = rk.json()
    matched = [x for x in items if x.get("id") in expected_ids and x.get("review_status") == "active"]
    if not matched:
        raise SystemExit("Keyword search returned no active seed products.")
    print(f"Keyword retrieval OK: {len(matched)} active seed products found.")

    settings = get_settings()
    if (settings.qdrant_url or "").strip():
        client_qdrant = get_qdrant_client()
        if client_qdrant is None:
            raise SystemExit("Qdrant URL exists, but client could not be created.")
        try:
            client_qdrant.get_collections()
        except Exception as exc:  # pragma: no cover - runtime env dependent
            raise SystemExit(f"Qdrant configured but unreachable: {exc}") from exc

        rs = client.get("/knowledge/products", params={"mode": "semantic", "q": "critical illness"})
        if rs.status_code != 200:
            raise SystemExit(f"Semantic search failed: {rs.status_code} {rs.text}")
        sem = rs.json()
        if not sem:
            raise SystemExit("Semantic search returned empty results with Qdrant configured.")
        if not any(x.get("match_reason") == "vector_qdrant" for x in sem):
            raise SystemExit("Qdrant configured, but semantic results did not use vector_qdrant.")
        print("Semantic retrieval OK: vector_qdrant results observed.")
    else:
        print("QDRANT_URL not configured; skipped qdrant semantic assertion.")


if __name__ == "__main__":
    main()

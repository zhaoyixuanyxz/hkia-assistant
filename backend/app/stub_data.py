from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data"


def load_product_stubs() -> list[dict]:
    with open(_DATA / "product_stubs.json", encoding="utf-8") as f:
        return json.load(f)


def load_market_stubs() -> list[dict]:
    with open(_DATA / "market_stubs.json", encoding="utf-8") as f:
        return json.load(f)


def filter_products(q: str | None, category: str | None) -> list[dict]:
    rows = load_product_stubs()
    if category:
        c = category.strip()
        rows = [r for r in rows if r.get("category") == c]
    if q:
        t = q.strip().lower()
        rows = [
            r
            for r in rows
            if t in r.get("name", "").lower() or t in r.get("summary", "").lower()
        ]
    return rows


MARKET_LAST_MOCK_REFRESH: datetime | None = None


def touch_market_mock_refresh() -> datetime:
    global MARKET_LAST_MOCK_REFRESH
    MARKET_LAST_MOCK_REFRESH = datetime.utcnow()
    return MARKET_LAST_MOCK_REFRESH

"""Upsert MarketIndicator rows from backend/app/data/market_stubs.json (no job record)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
load_dotenv(REPO_ROOT / ".env")

from app import db as db_mod  # noqa: E402
from app.models import MarketIndicator  # noqa: E402
from app.stub_data import load_market_stubs  # noqa: E402


def main() -> None:
    if db_mod.SessionLocal is None:
        db_mod.init_engine()
    db_mod.create_tables()
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        now = datetime.utcnow()
        stubs = load_market_stubs()
        for item in stubs:
            mid = str(item.get("id", ""))
            if not mid:
                continue
            row = s.get(MarketIndicator, mid)
            if row is None:
                row = MarketIndicator(id=mid)
                s.add(row)
            row.name = str(item.get("name", ""))
            row.value_text = str(item.get("value", ""))
            row.explanation = str(item.get("explanation", ""))
            row.source_url = str(item.get("source_url", ""))
            row.trend_note = str(item.get("trend_note", ""))
            row.updated_at = now
        s.commit()
        print(f"Synced {len(stubs)} market indicators from market_stubs.json.")
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


if __name__ == "__main__":
    main()

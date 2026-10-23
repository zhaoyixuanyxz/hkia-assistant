"""Scheduler entry: python -m app.jobs.monthly_product_fields_cli

Idempotent for the calendar month: if a successful monthly_product_fields job
already exists for the current Hong Kong month, exit 0 without re-fetching.
"""

from __future__ import annotations

import ssl
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import db as db_mod
from app.models import DataUpdateJob, Product
from app.monthly_product_fields import JOB_TYPE, run_monthly_product_fields
from app.product_fields_extract import allowed_product_url, excerpt_month_start

HK = ZoneInfo("Asia/Hong_Kong")
UA = "Mozilla/5.0 (compatible; hkia-assistant-monthly-fields/1.0)"


def _http_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def _already_succeeded_this_month(db, month_iso: str) -> bool:
    """Seal the month only when a success actually wrote products."""
    row = db.scalar(
        select(DataUpdateJob)
        .where(
            DataUpdateJob.job_type == JOB_TYPE,
            DataUpdateJob.status == "success",
            DataUpdateJob.detail_json.is_not(None),
            DataUpdateJob.detail_json["excerpt_month"].as_string() == month_iso,
            DataUpdateJob.detail_json["updated_count"].as_integer() > 0,
        )
        .order_by(DataUpdateJob.id.desc())
        .limit(1)
    )
    return row is not None


def main() -> int:
    if db_mod.SessionLocal is None:
        db_mod.init_engine()
        db_mod.create_tables()
    now = datetime.now(tz=HK)
    month = excerpt_month_start(now)
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        if _already_succeeded_this_month(s, month.isoformat()):
            print(f"skip: already succeeded for {month.isoformat()}")
            return 0
        urls = [
            r.official_url
            for r in s.scalars(select(Product).where(Product.review_status == "active")).all()
            if allowed_product_url(r.official_url or "")
        ]
        job = run_monthly_product_fields(db=s, product_urls=urls, fetch=_http_fetch, now=now)
        s.commit()
        print(f"job_id={job.id} status={job.status} detail={job.detail_json}")
        return 0 if job.status == "success" else 1
    finally:
        s.close()


if __name__ == "__main__":
    raise SystemExit(main())

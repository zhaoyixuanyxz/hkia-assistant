from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataUpdateJob, Product, ProductSource
from app.product_fields_extract import (
    allowed_product_url,
    excerpt_month_start,
    extract_sum_and_premium,
)

FetchFn = Callable[[str], str]
JOB_TYPE = "monthly_product_fields"


def run_monthly_product_fields(
    *,
    db: Session,
    product_urls: Sequence[str],
    fetch: FetchFn,
    now: datetime,
) -> DataUpdateJob:
    job = DataUpdateJob(job_type=JOB_TYPE, status="pending")
    db.add(job)
    db.flush()
    month = excerpt_month_start(now)
    updated = 0
    skipped = 0
    no_single = 0
    try:
        for url in product_urls:
            if not allowed_product_url(url):
                skipped += 1
                continue
            html = fetch(url)
            extracted = extract_sum_and_premium(html)
            product = db.scalar(select(Product).where(Product.official_url == url))
            if product is None:
                skipped += 1
                continue
            product.sum_assured = extracted.sum_assured
            product.premium = extracted.premium
            product.excerpt_date = month
            raw: dict[str, Any] = {
                "no_single_number": extracted.no_single_number,
                "excerpt_month": month.isoformat(),
                "source_url": url,
            }
            if extracted.no_single_number:
                no_single += 1
            db.add(
                ProductSource(
                    product_id=product.id,
                    kind="monthly_auto",
                    ref=url,
                    raw_json=raw,
                )
            )
            updated += 1
        job.status = "success"
        job.finished_at = datetime.utcnow()
        job.detail_json = {
            "updated_count": updated,
            "skipped_count": skipped,
            "no_single_number_count": no_single,
            "excerpt_month": month.isoformat(),
        }
    except Exception as exc:
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        job.error_message = str(exc)
        job.detail_json = {
            "updated_count": updated,
            "skipped_count": skipped,
            "no_single_number_count": no_single,
            "excerpt_month": month.isoformat(),
        }
    return job

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_mod
from app.models import Product, ProductSource
from app.monthly_product_fields import run_monthly_product_fields

HK = ZoneInfo("Asia/Hong_Kong")
FIXTURES = Path(__file__).parent / "fixtures" / "product_pages"


def test_hand_seed_scripts_are_not_monthly_job_type() -> None:
    """US-5 pass requires job_type monthly_product_fields, not seed imports."""
    from app.monthly_product_fields import JOB_TYPE

    assert JOB_TYPE == "monthly_product_fields"
    assert JOB_TYPE != "manual"


def test_product_model_has_sum_premium_excerpt_fields(api_client: TestClient) -> None:
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        p = Product(
            id="prod-fields-smoke",
            name="smoke",
            category="医疗",
            sum_assured="HKD 1,000,000",
            premium="HKD 500",
            excerpt_date=date(2026, 10, 1),
        )
        s.add(p)
        s.commit()
        row = s.get(Product, "prod-fields-smoke")
        assert row is not None
        assert row.sum_assured == "HKD 1,000,000"
        assert row.premium == "HKD 500"
        assert row.excerpt_date == date(2026, 10, 1)
    finally:
        s.close()


def _seed_product(url: str, pid: str = "prod-cl-1") -> None:
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        row = s.get(Product, pid)
        if row:
            s.delete(row)
            s.flush()
        s.add(
            Product(
                id=pid,
                name="测试产品",
                category="医疗",
                official_url=url,
                review_status="active",
            )
        )
        s.commit()
    finally:
        s.close()


def test_run_writes_fields_from_fetch(api_client: TestClient) -> None:
    url = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/example-plan"
    _seed_product(url)
    html = (FIXTURES / "single_numbers.html").read_text(encoding="utf-8")

    def fetch(u: str) -> str:
        assert u == url
        return html

    when = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=fetch,
            now=when,
        )
        s.commit()
        assert job.status == "success"
        row = s.get(Product, "prod-cl-1")
        assert row is not None
        assert row.sum_assured == "HKD 1,000,000"
        assert row.premium == "HKD 500"
        assert row.excerpt_date == date(2026, 10, 1)
        sources = s.scalars(select(ProductSource).where(ProductSource.product_id == "prod-cl-1")).all()
        assert any(x.kind == "monthly_auto" for x in sources)
        assert any(
            (x.raw_json or {}).get("no_single_number") is False for x in sources if x.kind == "monthly_auto"
        )
    finally:
        s.close()


def test_run_no_single_number_leaves_empty(api_client: TestClient) -> None:
    url = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/range-plan"
    _seed_product(url, pid="prod-cl-2")
    html = (FIXTURES / "no_single_number.html").read_text(encoding="utf-8")

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=lambda u: html,
            now=datetime(2026, 10, 15, 12, 0, tzinfo=HK),
        )
        s.commit()
        assert job.status == "success"
        row = s.get(Product, "prod-cl-2")
        assert row is not None
        assert row.sum_assured is None
        assert row.premium is None
        assert row.excerpt_date == date(2026, 10, 1)
        src = s.scalars(
            select(ProductSource).where(
                ProductSource.product_id == "prod-cl-2", ProductSource.kind == "monthly_auto"
            )
        ).one()
        assert src.raw_json["no_single_number"] is True
    finally:
        s.close()


def test_run_rejects_non_chinalife_url(api_client: TestClient) -> None:
    url = "https://www.example.com/products/insurance/medical/x"
    _seed_product(url, pid="prod-bad")
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=lambda u: "<html></html>",
            now=datetime(2026, 10, 15, 12, 0, tzinfo=HK),
        )
        s.commit()
        assert job.status == "success"
        row = s.get(Product, "prod-bad")
        assert row is not None
        assert row.sum_assured is None
        assert row.excerpt_date is None
    finally:
        s.close()


def test_run_fetch_failure_marks_job_failed(api_client: TestClient) -> None:
    url = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/example-plan"
    _seed_product(url, pid="prod-cl-fail")

    def fetch(_u: str) -> str:
        raise TimeoutError("network down")

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=fetch,
            now=datetime(2026, 10, 15, 12, 0, tzinfo=HK),
        )
        s.commit()
        assert job.status == "failed"
        assert "network" in (job.error_message or "").lower() or "Timeout" in job.error_message
    finally:
        s.close()

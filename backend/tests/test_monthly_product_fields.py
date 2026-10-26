from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db as db_mod
from app.models import DataUpdateJob, Product, ProductSource
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


def test_us6_mid_fail_then_full_list_second_run(api_client: TestClient) -> None:
    """AC-1: next start after mid-fail is full batch, not resume-from-failed-url."""
    url1 = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/plan-a"
    url2 = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/plan-b"
    _seed_product(url1, pid="prod-us6-a")
    _seed_product(url2, pid="prod-us6-b")
    html = (FIXTURES / "single_numbers.html").read_text(encoding="utf-8")
    urls = [url1, url2]
    when = datetime(2026, 10, 15, 12, 0, tzinfo=HK)

    calls: list[str] = []

    def fetch_fail_second(u: str) -> str:
        calls.append(u)
        if u == url2:
            raise TimeoutError("network down on second product")
        return html

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job1 = run_monthly_product_fields(
            db=s, product_urls=urls, fetch=fetch_fail_second, now=when
        )
        s.commit()
        assert job1.status == "failed"
        assert "resume_from" not in (job1.detail_json or {})
        assert "next_url" not in (job1.detail_json or {})
        assert "cursor" not in (job1.detail_json or {})

        def fetch_ok(u: str) -> str:
            calls.append(u)
            return html

        job2 = run_monthly_product_fields(
            db=s, product_urls=urls, fetch=fetch_ok, now=when
        )
        s.commit()
        assert job2.status == "success"
        # Second run must hit the full list (both URLs), not only url2
        second_run_urls = calls[calls.index(url2) + 1 :]  # after the failing call
        assert url1 in second_run_urls and url2 in second_run_urls

        for pid in ("prod-us6-a", "prod-us6-b"):
            row = s.get(Product, pid)
            assert row is not None
            assert row.excerpt_date == date(2026, 10, 1)

        # No job detail ever carries a resume cursor key
        jobs = s.scalars(select(DataUpdateJob).where(DataUpdateJob.job_type == "monthly_product_fields")).all()
        for j in jobs:
            detail = j.detail_json or {}
            assert "resume_from" not in detail
            assert "next_url" not in detail
            assert "cursor" not in detail
    finally:
        s.close()


def test_us6_failed_job_does_not_seal_month(api_client: TestClient) -> None:
    """AC-2: operator can start next run without hand-editing a breakpoint."""
    from app.jobs.monthly_product_fields_cli import _already_succeeded_this_month
    from app.monthly_product_fields import JOB_TYPE

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        month_iso = "2026-10-01"
        s.add(
            DataUpdateJob(
                job_type=JOB_TYPE,
                status="failed",
                error_message="network down",
                detail_json={
                    "updated_count": 1,
                    "skipped_count": 0,
                    "no_single_number_count": 0,
                    "excerpt_month": month_iso,
                },
            )
        )
        s.commit()
        assert _already_succeeded_this_month(s, month_iso) is False
    finally:
        s.close()

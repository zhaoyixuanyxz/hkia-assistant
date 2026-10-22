from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.product_fields_extract import (
    allowed_product_url,
    excerpt_month_start,
    extract_sum_and_premium,
)

FIXTURES = Path(__file__).parent / "fixtures" / "product_pages"
HK = ZoneInfo("Asia/Hong_Kong")


def test_allowed_product_url_accepts_chinalife_product_page() -> None:
    assert allowed_product_url(
        "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/example-plan"
    )
    assert allowed_product_url(
        "https://chinalife.com.hk/zh-hk/products/insurance/savings/foo"
    )


def test_allowed_product_url_rejects_others() -> None:
    assert not allowed_product_url("https://www.example.com/products/insurance/x")
    assert not allowed_product_url("https://www.chinalife.com.hk/zh-hk/about")
    assert not allowed_product_url("https://www.chinalife.com.hk/zh-hk/products/insurance")


def test_excerpt_month_start_hong_kong() -> None:
    # 2026-10-31 23:30 UTC == 2026-11-01 07:30 HKT → November
    dt = datetime(2026, 10, 31, 23, 30, tzinfo=ZoneInfo("UTC"))
    assert excerpt_month_start(dt) == datetime(2026, 11, 1, tzinfo=HK).date()


def test_extract_single_numbers() -> None:
    html = (FIXTURES / "single_numbers.html").read_text(encoding="utf-8")
    result = extract_sum_and_premium(html)
    assert result.sum_assured == "HKD 1,000,000"
    assert result.premium == "HKD 500"
    assert result.no_single_number is False


def test_extract_no_single_number() -> None:
    html = (FIXTURES / "no_single_number.html").read_text(encoding="utf-8")
    result = extract_sum_and_premium(html)
    assert result.sum_assured is None
    assert result.premium is None
    assert result.no_single_number is True


def test_extract_short_label_inside_longer_word_rejects() -> None:
    """保额 inside 最高保額 must not be treated as a sum-assured label."""
    html = (FIXTURES / "compound_label_ceiling.html").read_text(encoding="utf-8")
    result = extract_sum_and_premium(html)
    assert result.sum_assured is None
    assert result.premium is None
    assert result.no_single_number is True

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.report_products import (
    enrich_product_picks_with_sources,
    filter_picks_current_excerpt_month,
    filter_picks_requiring_three_fields,
    hydrate_concrete_picks_from_candidates,
)
from app.schemas import ReportPayload, ReportProductPick

HK = ZoneInfo("Asia/Hong_Kong")


def test_hydrate_fills_when_model_left_picks_empty() -> None:
    payload = ReportPayload(
        title="t",
        concrete_product_picks=[],
    )
    cands = [
        {
            "product_id": "p1",
            "name": "演示产品一",
            "match_reason": "命中",
            "source_url": "https://example.com/a",
        },
        {
            "product_id": "p2",
            "name": "演示产品二",
            "match_reason": "",
            "source_url": "",
        },
    ]
    out = hydrate_concrete_picks_from_candidates(payload, cands, max_picks=3)
    assert len(out.concrete_product_picks) == 2
    assert out.concrete_product_picks[0].product_id == "p1"
    assert out.concrete_product_picks[0].rationale == "命中"
    assert out.concrete_product_picks[1].product_id == "p2"
    assert len(out.concrete_product_picks[1].rationale) > 10


def test_hydrate_noop_when_picks_already_present() -> None:
    payload = ReportPayload(
        title="t",
        concrete_product_picks=[
            ReportProductPick(product_id="p1", name="x", rationale="y"),
        ],
    )
    cands = [{"product_id": "p2", "name": "other", "match_reason": "", "source_url": ""}]
    out = hydrate_concrete_picks_from_candidates(payload, cands)
    assert len(out.concrete_product_picks) == 1
    assert out.concrete_product_picks[0].product_id == "p1"


def test_enrich_copies_sum_premium_excerpt_from_candidate() -> None:
    payload = ReportPayload(
        concrete_product_picks=[
            ReportProductPick(product_id="p1", name="旧名", rationale="", source_url="")
        ]
    )
    cmap = {
        "p1": {
            "name": "产品甲",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/x",
            "match_reason": "match",
            "sum_assured": "HKD 1,000,000",
            "premium": "HKD 500",
            "excerpt_date": "2026-10-01",
        }
    }
    out = enrich_product_picks_with_sources(payload, cmap)
    pick = out.concrete_product_picks[0]
    assert pick.sum_assured == "HKD 1,000,000"
    assert pick.premium == "HKD 500"
    assert pick.excerpt_date == "2026-10-01"


def _pick(**kwargs) -> ReportProductPick:
    base = dict(
        product_id="p1",
        name="n",
        rationale="r",
        sum_assured="HKD 1",
        premium="HKD 2",
        excerpt_date="2026-10-01",
    )
    base.update(kwargs)
    return ReportProductPick(**base)


def test_filter_drops_missing_sum_assured() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick(sum_assured=None)])
    out = filter_picks_requiring_three_fields(payload)
    assert out.concrete_product_picks == []


def test_filter_drops_missing_premium() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick(premium="  ")])
    out = filter_picks_requiring_three_fields(payload)
    assert out.concrete_product_picks == []


def test_filter_drops_missing_excerpt_date() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick(excerpt_date=None)])
    out = filter_picks_requiring_three_fields(payload)
    assert out.concrete_product_picks == []


def test_filter_keeps_complete_pick() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick()])
    out = filter_picks_requiring_three_fields(payload)
    assert len(out.concrete_product_picks) == 1
    assert out.concrete_product_picks[0].product_id == "p1"


def test_filter_drops_pick_after_locale_rewrite_strips_three_fields() -> None:
    """Simulates post-llm_rewrite_report_locale picks missing numeric/date fields."""
    payload = ReportPayload(concrete_product_picks=[_pick()])
    rewritten = payload.model_copy(
        update={
            "concrete_product_picks": [
                _pick(sum_assured=None, premium=None, excerpt_date=None)
            ]
        }
    )
    out = filter_picks_requiring_three_fields(rewritten)
    assert out.concrete_product_picks == []


def test_filter_after_hydrate_drops_incomplete_candidate() -> None:
    payload = ReportPayload(concrete_product_picks=[])
    cands = [
        {
            "product_id": "bad",
            "name": "ç¼ºä¿é¢",
            "match_reason": "x",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/x",
            "sum_assured": None,
            "premium": "HKD 1",
            "excerpt_date": "2026-10-01",
        },
        {
            "product_id": "good",
            "name": "é½å…¨",
            "match_reason": "y",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/y",
            "sum_assured": "HKD 9",
            "premium": "HKD 1",
            "excerpt_date": "2026-10-01",
        },
    ]
    mid = hydrate_concrete_picks_from_candidates(payload, cands, max_picks=3)
    out = filter_picks_requiring_three_fields(mid)
    ids = [p.product_id for p in out.concrete_product_picks]
    assert ids == ["good"]


def test_month_filter_drops_earlier_month() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-09-30")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert out.concrete_product_picks == []


def test_month_filter_keeps_same_month() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-10-01")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert len(out.concrete_product_picks) == 1


def test_month_filter_keeps_yyyy_mm() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-10")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert len(out.concrete_product_picks) == 1


def test_month_filter_drops_unparseable() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="not-a-month")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert out.concrete_product_picks == []


def test_month_filter_uses_hk_boundary_now() -> None:
    # Just into October HK; September excerpt must drop.
    now = datetime(2026, 10, 1, 0, 5, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-09-30")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert out.concrete_product_picks == []

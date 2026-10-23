from __future__ import annotations

from app.report_products import (
    enrich_product_picks_with_sources,
    hydrate_concrete_picks_from_candidates,
)
from app.schemas import ReportPayload, ReportProductPick


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

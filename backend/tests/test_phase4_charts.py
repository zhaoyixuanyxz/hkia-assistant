"""Phase 4: chart sanitization + parse_report_json coercion."""

from __future__ import annotations

import json

import pytest

from app.chart_spec import (
    ALLOWED_CHART_TYPES,
    GLOBAL_MAX_REPORT_CHARTS,
    sanitize_chart_item,
    sanitize_charts_list,
)
from app.llm import parse_report_json, report_fallback
from app.schemas import ChartSpec, ReportPayload


def test_parse_report_json_strips_preamble_and_trailing_noise() -> None:
    base = {
        "title": "T",
        "user_background": "u",
        "insights": "i",
        "allocation_direction": "a",
        "product_category_suggestions": "p",
        "risk_notes": "r",
        "follow_up_questions": [],
        "limited_data_notice": "l",
        "disclaimer": "d",
        "charts": [{"type": "pie", "title": "x", "data": [{"name": "a", "value": 1}]}],
        "concrete_product_picks": [],
    }
    dumped = json.dumps(base, ensure_ascii=False)
    raw = f'说明文字在前：\n{dumped}\n（以上为生成结果）'
    p = parse_report_json(raw)
    assert p.title == "T"
    assert len(p.charts) >= 1


def test_parse_report_json_coerces_follow_up_question_string_to_list() -> None:
    base = {
        "title": "T",
        "user_background": "u",
        "insights": "i",
        "allocation_direction": "a",
        "product_category_suggestions": "p",
        "risk_notes": "r",
        "follow_up_questions": "请补充币种偏好",
        "limited_data_notice": "l",
        "disclaimer": "",
        "charts": [],
        "concrete_product_picks": [],
    }
    dumped = json.dumps(base, ensure_ascii=False)
    p = parse_report_json(dumped)
    assert p.follow_up_questions == ["请补充币种偏好"]


def test_allowed_chart_types_count() -> None:
    assert len(ALLOWED_CHART_TYPES) >= 12


@pytest.mark.parametrize(
    "ctype",
    sorted(ALLOWED_CHART_TYPES),
)
def test_sanitize_accepts_each_type(ctype: str) -> None:
    row = {"type": ctype, "title": "t", "data": [{"name": "x", "value": 1}]}
    out = sanitize_chart_item(row)
    assert out is not None
    assert out["type"] == ctype
    ReportPayload(title="x", charts=[ChartSpec(**out)])


def test_sanitize_rejects_unknown_type() -> None:
    assert sanitize_chart_item({"type": "waterfall", "title": "", "data": [{"name": "a", "value": 1}]}) is None


def test_sanitize_drops_when_no_valid_rows() -> None:
    assert sanitize_chart_item({"type": "pie", "title": "x", "data": []}) is None


def test_sanitize_keeps_numeric_coercion_rows() -> None:
    """Rows with junk keys still normalize to numeric value."""
    out = sanitize_chart_item(
        {
            "type": "pie",
            "title": "x",
            "data": [{"oops": True}, {"name": "a", "value": "3"}],
        }
    )
    assert out is not None
    raw = json.dumps(
        {
            "title": "T",
            "user_background": "u",
            "insights": "i",
            "allocation_direction": "a",
            "product_category_suggestions": "p",
            "risk_notes": "r",
            "follow_up_questions": [],
            "limited_data_notice": "l",
            "disclaimer": "d",
            "charts": [
                {"type": "bad_typo", "title": "", "data": [{"name": "a", "value": 5}]},
                {"type": "bar", "title": "预算对比", "data": [{"name": "医疗", "value": 60}]},
            ],
        },
        ensure_ascii=False,
    )
    payload = parse_report_json(raw)
    assert len(payload.charts) == 1
    assert payload.charts[0].type == "bar"


def test_report_fallback_charts_remain_valid() -> None:
    fb = report_fallback()
    assert sanitize_charts_list([c.model_dump() for c in fb.charts])


def test_charts_truncated_when_over_capacity_via_schema() -> None:
    types_cycle = sorted(ALLOWED_CHART_TYPES)
    specs = []
    for i in range(GLOBAL_MAX_REPORT_CHARTS + 3):
        t = types_cycle[i % len(types_cycle)]
        specs.append(
            ChartSpec(type=t, title=str(i), data=[{"name": "n", "value": float(i)}])  # type: ignore[arg-type]
        )
    p = ReportPayload(title="many", charts=specs)
    assert len(p.charts) == GLOBAL_MAX_REPORT_CHARTS

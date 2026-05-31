from __future__ import annotations

from fastapi.testclient import TestClient

from app.chart_spec import ChartBudget, compute_chart_budget, enforce_report_chart_depth
from app.survey_merge import survey_to_dimension_strings
from app.survey_template import (
    compute_report_depth,
    count_filled_optional,
    validate_survey_answers,
)


def _full_answers(extra_opt: bool = False) -> dict:
    a = {
        "age_band": "25-34",
        "residency_region": "香港",
        "marital_dependents_summary": "单身",
        "occupation_category": "雇员（办公室）",
        "income_band": "每月可动用收入：2万-5万港币",
        "premium_afford_ratio_band": "10%-20%",
        "primary_goals": ["medical_hospital"],
        "smoking": "否",
        "health_notes": "",
        "existing_coverage_summary": "",
        "mortgage_debts_band": "",
        "liquid_assets_band": "",
        "education_funding_note": "",
        "target_retirement_age": "",
        "mpf_note": "",
        "currency_preference": "",
        "existing_policies_free_text": "",
    }
    if extra_opt:
        a["existing_coverage_summary"] = "无"
        a["mortgage_debts_band"] = "无或极少"
        a["liquid_assets_band"] = "10-50万"
        a["education_funding_note"] = "暂不需要"
        a["target_retirement_age"] = "65"
        a["mpf_note"] = "标准供款"
        a["existing_policies_free_text"] = "公司团险"
        a["health_notes"] = "良好"
        a["currency_preference"] = "港币"
    return a


def test_validate_survey_answers_requires_goals() -> None:
    a = _full_answers()
    a["primary_goals"] = []
    try:
        validate_survey_answers(a)
    except ValueError as e:
        assert "目标" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_report_depth_tiers() -> None:
    base = validate_survey_answers(_full_answers())
    assert compute_report_depth(base) == "standard"
    assert count_filled_optional(base) < 4

    deep_answers = validate_survey_answers(_full_answers(extra_opt=True))
    assert compute_report_depth(deep_answers) == "deep"


def test_enforce_chart_depth_distinct_types() -> None:
    one = [{"type": "pie", "title": "a", "data": [{"name": "x", "value": 1}]}]
    out = enforce_report_chart_depth(one, "enhanced")
    assert len(out) >= 3
    assert len({c["type"] for c in out}) >= 3


def test_chart_budget_more_optional_and_structure_raises_cap() -> None:
    sparse = compute_chart_budget("standard", optional_filled=0, structured={"dimensions": {"goals": "x"}})
    rich = compute_chart_budget(
        "deep",
        optional_filled=10,
        structured={
            "dimensions": {"goals": "长期医疗与退休金衔接" * 3, "family": "供养父母与二孩" * 4},
            "product_focus_categories": ["医疗", "人寿", "重疾"],
            "key_memories": ["m1", "m2"],
            "budget_hint": "可动用月入与保费比例已披露",
        },
    )
    assert sparse.max_charts < rich.max_charts
    assert rich.max_charts >= 14


def test_enforce_chart_depth_respects_custom_budget_ceiling() -> None:
    b = ChartBudget(max_charts=5, min_distinct_types=3, target_min_count=5)
    out = enforce_report_chart_depth([], "deep", budget=b)
    assert len(out) == 5
    assert len({c["type"] for c in out}) >= min(3, len(out))


def test_survey_to_dimension_strings() -> None:
    a = validate_survey_answers(_full_answers())
    d = survey_to_dimension_strings(a)
    assert "25-34" in d["life_stage"]
    assert "香港" in d["life_stage"]
    assert d["finance"]


def test_generate_report_422_without_survey(api_client: TestClient) -> None:
    r = api_client.post(
        "/auth/register",
        json={
            "email": "nosurvey@example.com",
            "password": "secret12",
            "display_name": "N",
        },
    )
    assert r.status_code == 200
    r = api_client.post(
        "/auth/login",
        json={"email": "nosurvey@example.com", "password": "secret12"},
    )
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = api_client.post("/conversations", json={"title": "n"}, headers=h)
    cid = r.json()["id"]
    for i in range(2):
        api_client.post(
            f"/conversations/{cid}/messages",
            json={"content": f"m{i}"},
            headers=h,
        )
    rep = api_client.post(f"/conversations/{cid}/reports/generate", headers=h)
    assert rep.status_code == 422

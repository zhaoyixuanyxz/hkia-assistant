from __future__ import annotations

from app.report_locale_enforce import (
    field_needs_target_language_rewrite,
    force_survey_derived_fields_to_locale,
    report_payload_needs_locale_rewrite,
)
from app.schemas import ReportPayload, ReportProductPick
from app.survey_template import validate_survey_answers


def _sample_answers() -> dict:
    return validate_survey_answers(
        {
            "age_band": "25-34",
            "residency_region": "香港",
            "marital_dependents_summary": "Married, one child",
            "occupation_category": "雇员（办公室）",
            "income_band": "每月可动用收入：1万-2万港币",
            "premium_afford_ratio_band": "10%-20%",
            "primary_goals": ["medical_hospital", "critical_illness"],
            "smoking": "否",
            "existing_coverage_summary": "",
            "mortgage_debts_band": "",
            "liquid_assets_band": "",
            "health_notes": "",
            "education_funding_note": "",
            "target_retirement_age": "",
            "mpf_note": "",
            "currency_preference": "",
            "existing_policies_free_text": "",
        }
    )


def test_field_needs_rewrite_detects_chinese() -> None:
    assert field_needs_target_language_rewrite(
        "建议优先建立医疗与重疾保障防线。", locale="en"
    )
    assert not field_needs_target_language_rewrite(
        "Prioritise medical and critical-illness cover.", locale="en"
    )
    assert not field_needs_target_language_rewrite(
        "建议优先建立医疗保障。", locale="zh-CN"
    )


def test_report_payload_needs_locale_rewrite_on_mixed() -> None:
    p = ReportPayload(
        title="中国人寿海外保障规划参考报告",
        user_background="English enough background text without han.",
        insights="Insights in English about disposable income banding.",
        allocation_direction="建议优先建立医疗与重疾保障防线。",
        product_category_suggestions="医疗、重疾",
        risk_notes="Risk note in English only.",
        follow_up_questions=[],
        charts=[{"type": "pie", "title": "保障优先级", "data": [{"name": "医疗", "value": 1}]}],
        concrete_product_picks=[
            ReportProductPick(
                product_id="x",
                name="衛您健康",
                rationale="可作为住院医疗保障的第一道防线。",
                source_url="",
            )
        ],
    )
    assert report_payload_needs_locale_rewrite(p, "en")
    assert not report_payload_needs_locale_rewrite(p, "zh-CN")


def test_force_survey_derived_fields_english() -> None:
    a = _sample_answers()
    p = ReportPayload(
        title="中国人寿海外保障规划参考报告",
        user_background="由于缺乏年龄、收入等具体画像信息，无法个性化。",
        insights="缺乏具体信息。",
        allocation_direction="建议优先建立医疗与重疾保障防线。",
        product_category_suggestions="医疗、重疾",
        risk_notes="条款以正式文件为准。",
        follow_up_questions=[],
        charts=[],
        concrete_product_picks=[],
    )
    out = force_survey_derived_fields_to_locale(p, a, locale="en")
    assert "Age band" in out.user_background or "25-34" in out.user_background
    assert "根据用户" not in out.user_background
    assert "由于缺乏" not in out.user_background
    assert "Hospital" in out.product_category_suggestions or "Medical" in out.product_category_suggestions
    assert "医疗" not in out.product_category_suggestions
    assert "Priorit" in out.allocation_direction or "focus" in out.allocation_direction.lower()
    assert "建议优先" not in out.allocation_direction
    assert "China Life" in out.title or "Planning" in out.title
    assert "中国人寿" not in out.title

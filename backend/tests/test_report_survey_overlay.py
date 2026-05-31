from __future__ import annotations

from app.report_survey_overlay import (
    _text_denies_known_survey_prose,
    overlay_report_when_model_ignores_survey,
    prune_follow_up_questions_after_survey_merge,
)
from app.schemas import ReportPayload
from app.survey_template import validate_survey_answers


def _sample_answers() -> dict:
    return validate_survey_answers(
        {
            "age_band": "25-34",
            "residency_region": "香港",
            "marital_dependents_summary": "已婚一孩",
            "occupation_category": "雇员（办公室）",
            "income_band": "每月可动用收入：2万-5万港币",
            "premium_afford_ratio_band": "10%-20%",
            "primary_goals": ["medical_hospital"],
            "existing_coverage_summary": "",
            "mortgage_debts_band": "",
            "liquid_assets_band": "",
            "smoking": "否",
            "health_notes": "",
            "education_funding_note": "",
            "target_retirement_age": "",
            "mpf_note": "",
            "currency_preference": "",
            "existing_policies_free_text": "",
        }
    )


def test_text_denies_known_survey_prose_chinese() -> None:
    assert _text_denies_known_survey_prose("用户目前未提供详细的个人背景信息，包括年龄与收入。")
    assert not _text_denies_known_survey_prose(
        "用户自述年龄区间 25-34，常住香港，核心目标为医疗保障，可承受保费约占收入 10%-20%。"
    )


def test_text_denies_english() -> None:
    assert _text_denies_known_survey_prose(
        "Due to a lack of specific user information, we cannot personalize."
    )


def test_overlay_replaces_zh_zanwei_user_background() -> None:
    """Regression: wording「背景信息暂未提供」used to bypass regex 「未提供…背景」."""
    a = _sample_answers()
    p = ReportPayload(
        title="t",
        user_background=(
            "用户背景信息暂未提供，请补充年龄、收入、家庭状况及保障目标等关键信息"
            "以生成更精准的配置建议。"
        ),
        insights="结合核心目标可作配置讨论；收入亦可作约束。（模型部分正确示例）",
        allocation_direction="x",
        product_category_suggestions="y",
        risk_notes="z",
        follow_up_questions=[],
        charts=[],
        concrete_product_picks=[],
    )
    out = overlay_report_when_model_ignores_survey(p, a)
    assert "25-34" in out.user_background
    assert "香港" in out.user_background


def test_prune_follow_up_drops_template_when_survey_already_covers() -> None:
    a = validate_survey_answers(
        {
            **_sample_answers(),
            "existing_coverage_summary": "公司团体医疗计划，暂无个人商业寿险。",
        }
    )
    merged = {
        "dimensions": {"family": "已婚一孩"},
        "key_memories": ["样本记忆"],
    }
    p = ReportPayload(
        title="t",
        user_background="u",
        insights="i",
        allocation_direction="",
        product_category_suggestions="",
        risk_notes="",
        follow_up_questions=[
            "您的年龄区间及是否有受供养家庭成员？",
            "您目前的年收入及可承受的年度保费预算范围？",
            "您是否已有其他商业保险或公司团体保障？",
            "您对医疗险的住院病房级别或地域覆盖是否有特殊要求？",
        ],
        charts=[],
        concrete_product_picks=[],
    )
    out = prune_follow_up_questions_after_survey_merge(p, a, merged)
    joined = "".join(out.follow_up_questions)
    assert "年龄" not in joined
    assert len(out.follow_up_questions) <= 1


def test_overlay_replaces_boilerplate() -> None:
    a = _sample_answers()
    p = ReportPayload(
        title="t",
        user_background="The user has not yet provided detailed personal background.",
        insights="Due to lack of user information, no personalized insights.",
        allocation_direction="generic",
        product_category_suggestions="medical",
        risk_notes="x",
        follow_up_questions=[],
        charts=[],
        concrete_product_picks=[],
    )
    out = overlay_report_when_model_ignores_survey(p, a)
    assert "25-34" in out.user_background
    assert "香港" in out.user_background
    assert "住院与医疗费用保障" in out.user_background
    assert "2万-5万" in out.insights

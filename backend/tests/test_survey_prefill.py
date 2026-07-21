from __future__ import annotations

from app.survey_prefill import (
    infer_survey_draft_from_chat,
    merge_survey_fill_blanks_only,
)
from app.survey_template import _blankish, coerce_survey_answers


def test_merge_survey_fill_blanks_only_keeps_existing() -> None:
    existing = coerce_survey_answers(
        {
            "age_band": "35-44",
            "residency_region": "",
            "primary_goals": ["wealth_savings"],
        }
    )
    inferred = coerce_survey_answers(
        {
            "age_band": "18-24",
            "residency_region": "香港",
            "occupation_category": "学生/待业",
            "primary_goals": ["medical_hospital", "critical_illness"],
        }
    )
    merged = merge_survey_fill_blanks_only(existing, inferred)
    assert merged["age_band"] == "35-44"
    assert merged["residency_region"] == "香港"
    assert merged["occupation_category"] == "学生/待业"
    assert merged["primary_goals"] == ["wealth_savings"]


def test_infer_from_conv19_style_profile() -> None:
    structured = {
        "summary_text": (
            "用户为24岁男性，从不吸烟，处于风险保障规划初期。"
            "预算每月约1000-4000港币，主要担忧意外或大病导致的医疗费用及收入中断风险。"
            "已明确表达对住院医疗险和重疾险的配置意向。"
            "自述非常健康，无既往病史。"
        ),
        "dimensions": {
            "finance": "预算每月1000-4000港币，处于保障规划初期",
            "family": "单身",
            "health": "非常健康，无既往病史或长期服药情况，从不吸烟",
            "goals": "担忧意外或大病，意向配置住院医疗险和重疾险",
            "risk_appetite": "接受较高垫底费以降低保费",
            "life_stage": "24岁年轻单身人士",
            "values": "务实",
        },
        "key_memories": [
            "24岁，男性，从不吸烟",
            "预算每月约1000-4000港币",
            "意向配置住院医疗险和重疾险",
            "接受先医疗、后重疾的优先次序建议",
            "调查表-年龄区间：18-24",
            "调查表-家庭责任：单身",
            "调查表-核心目标：身故/意外/伤残保障、重大疾病、住院/医疗",
        ],
        "product_focus_categories": ["医疗", "重疾", "人寿"],
        "budget_hint": "每月约1000-4000港币（调查表：每月可动用收入：1万-2万港币；10%-20%）",
    }
    draft = infer_survey_draft_from_chat(
        summary_text=structured["summary_text"],
        structured=structured,
        user_messages=[
            "暂时没有买过任何保险",
            "没有香港身份，但是有计划长期留港发展",
            "都没有，非常健康",
        ],
    )
    assert draft["age_band"] == "18-24"
    assert draft["residency_region"] == "香港"
    assert draft["marital_dependents_summary"] == "单身"
    assert draft["occupation_category"] == "学生/待业"
    assert draft["income_band"] == "每月可动用收入：1万-2万港币"
    assert draft["premium_afford_ratio_band"] == "10%-20%"
    assert "medical_hospital" in draft["primary_goals"]
    assert "critical_illness" in draft["primary_goals"]
    assert draft["smoking"] == "否"
    assert not _blankish(draft["health_notes"])
    assert not _blankish(draft["existing_coverage_summary"])


def test_infer_from_english_chat_profile() -> None:
    summary = (
        "The user is a 24-year-old male non-smoker, single, currently a student "
        "or between jobs, residing in Hong Kong without permanent identity yet, "
        "and plans to build a long-term career here. Monthly disposable income "
        "about HKD 10k–20k; comfortable putting 10%–20% toward insurance "
        "(about HKD 1,000–4,000 per month). Never bought any insurance. "
        "Very healthy. Wants hospital medical first, then critical illness."
    )
    draft = infer_survey_draft_from_chat(
        summary_text=summary,
        structured={
            "dimensions": {
                "family": "single",
                "life_stage": "24-year-old",
                "health": "non-smoker, very healthy",
                "goals": "hospital medical and critical illness",
            },
            "key_memories": [
                "24-year-old male non-smoker",
                "based in Hong Kong",
                "student / between jobs",
            ],
            "product_focus_categories": ["Medical", "Critical illness"],
            "budget_hint": "HKD 1,000–4,000 / month; 10%–20%",
        },
        user_messages=[
            "Hi. I'm 24, male, non-smoker, single, currently a student / between jobs, "
            "based in Hong Kong. Monthly disposable income HKD 10,000–20,000; "
            "10%–20% toward insurance. I have never bought any insurance. "
            "I'm very healthy. Please prioritize a hospital medical plan first, "
            "then critical illness."
        ],
    )
    assert draft["age_band"] == "18-24"
    assert draft["residency_region"] == "香港"
    assert draft["marital_dependents_summary"] == "单身"
    assert draft["occupation_category"] == "学生/待业"
    assert draft["income_band"] == "每月可动用收入：1万-2万港币"
    assert draft["premium_afford_ratio_band"] == "10%-20%"
    assert "medical_hospital" in draft["primary_goals"]
    assert "critical_illness" in draft["primary_goals"]
    assert draft["smoking"] == "否"
    assert not _blankish(draft["health_notes"])
    assert not _blankish(draft["existing_coverage_summary"])

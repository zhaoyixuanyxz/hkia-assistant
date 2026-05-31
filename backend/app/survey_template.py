"""Fixed HKIA report supplement survey template (v1): validation & depth scoring."""

from __future__ import annotations

from typing import Any, Literal

SURVEY_TEMPLATE_VERSION = "1"

ReportDepth = Literal["standard", "enhanced", "deep"]

# Required field ids
REQUIRED_FIELDS: tuple[str, ...] = (
    "age_band",
    "residency_region",
    "marital_dependents_summary",
    "occupation_category",
    "income_band",
    "premium_afford_ratio_band",
    "primary_goals",
)

OPTIONAL_FIELDS: tuple[str, ...] = (
    "existing_coverage_summary",
    "mortgage_debts_band",
    "liquid_assets_band",
    "smoking",
    "health_notes",
    "education_funding_note",
    "target_retirement_age",
    "mpf_note",
    "currency_preference",
    "existing_policies_free_text",
)

PRIMARY_GOAL_OPTIONS: tuple[str, ...] = (
    "death_disability",
    "medical_hospital",
    "critical_illness",
    "wealth_savings",
    "retirement_income",
    "education_legacy",
)


def _blankish(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return True
        if s in ("未知", "不清楚", "—", "-"):
            return True
        return False
    if isinstance(v, list):
        return len(v) == 0
    return False


def coerce_survey_answers(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize keys for draft saves (does not enforce required)."""
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}
    for key in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        out[key] = raw.get(key)

    pg = out.get("primary_goals")
    if not isinstance(pg, list):
        pg = []
    goals_norm: list[str] = []
    for x in pg:
        s = str(x).strip()
        if s and s not in goals_norm:
            goals_norm.append(s)
    out["primary_goals"] = goals_norm

    for rk in REQUIRED_FIELDS:
        if rk == "primary_goals":
            continue
        v = out.get(rk)
        out[rk] = (v if isinstance(v, str) else str(v or "")).strip()
    for ok in OPTIONAL_FIELDS:
        v = out.get(ok)
        out[ok] = (v if isinstance(v, str) else str(v or "")).strip()

    return out


def validate_survey_answers(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize and validate answers; raises ValueError with Chinese message on failure."""
    if raw is None:
        raise ValueError("调查表数据为空")
    if not isinstance(raw, dict):
        raise ValueError("调查表格式无效")

    out = coerce_survey_answers(raw)

    for rk in REQUIRED_FIELDS:
        if rk == "primary_goals":
            goals_norm = out.get("primary_goals") or []
            if not isinstance(goals_norm, list):
                goals_norm = []
            if not goals_norm:
                raise ValueError("请至少选择一项核心投保目标")
            invalid = [g for g in goals_norm if g not in PRIMARY_GOAL_OPTIONS]
            if invalid:
                raise ValueError("核心投保目标含无效选项")
            continue
        val = out.get(rk)
        if not isinstance(val, str) or _blankish(val):
            raise ValueError(f"必填项未填写完整：{rk}")

    for ok in OPTIONAL_FIELDS:
        v = out.get(ok)
        if v is None:
            out[ok] = ""
        elif isinstance(v, str):
            out[ok] = v.strip()
        else:
            out[ok] = str(v).strip()

    return out


def count_filled_optional(answers: dict[str, Any]) -> int:
    n = 0
    for k in OPTIONAL_FIELDS:
        if not _blankish(answers.get(k)):
            n += 1
    return n


def compute_report_depth(answers: dict[str, Any]) -> ReportDepth:
    """Assumes answers already validated (required complete)."""
    n = count_filled_optional(answers)
    if n >= 8:
        return "deep"
    if n >= 4:
        return "enhanced"
    return "standard"


def survey_answers_for_prompt(answers: dict[str, Any]) -> str:
    """Compact block for LLM prompts."""
    lines: list[str] = []
    label_map = {
        "age_band": "年龄区间",
        "residency_region": "常住/工作地",
        "marital_dependents_summary": "婚姻与供养责任",
        "occupation_category": "职业类别",
        "income_band": "收入区间",
        "premium_afford_ratio_band": "愿承担保费占收入比例",
        "primary_goals": "核心投保目标",
        "existing_coverage_summary": "现有寿险/重疾/医疗保障概述",
        "mortgage_debts_band": "按揭与其他负债",
        "liquid_assets_band": "流动资产",
        "smoking": "吸烟",
        "health_notes": "健康状况",
        "education_funding_note": "子女教育金关注点",
        "target_retirement_age": "目标退休年龄",
        "mpf_note": "强积金/供款线索",
        "currency_preference": "保单货币偏好",
        "existing_policies_free_text": "已有保单补充说明",
    }
    for k in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        v = answers.get(k)
        if k == "primary_goals" and isinstance(v, list):
            lines.append(f"- {label_map[k]}：{', '.join(v)}")
        elif not _blankish(v):
            lines.append(f"- {label_map[k]}：{v}")
    return "\n".join(lines)


def template_field_metadata() -> dict[str, Any]:
    """For GET /survey template endpoint (frontend renders from this)."""
    return {
        "version": SURVEY_TEMPLATE_VERSION,
        "required": [
            {
                "id": "age_band",
                "input": "select",
                "options": [
                    "18以下",
                    "18-24",
                    "25-34",
                    "35-44",
                    "45-54",
                    "55-64",
                    "65及以上",
                ],
            },
            {
                "id": "residency_region",
                "input": "select",
                "options": [
                    "香港",
                    "中国内地",
                    "澳门",
                    "台湾",
                    "其他",
                ],
            },
            {
                "id": "marital_dependents_summary",
                "input": "text",
                "placeholder": "例：单身无供养 / 已婚一孩需供养父母",
                "max_len": 500,
            },
            {
                "id": "occupation_category",
                "input": "select",
                "options": [
                    "雇员（办公室）",
                    "雇员（需体力劳动或外勤）",
                    "专业人士/自雇",
                    "企业主或股东",
                    "学生/待业",
                    "退休",
                    "其他",
                ],
            },
            {
                "id": "income_band",
                "input": "select",
                "options": [
                    "每月可动用收入：1万港币以下",
                    "每月可动用收入：1万-2万港币",
                    "每月可动用收入：2万-5万港币",
                    "每月可动用收入：5万-10万港币",
                    "每月可动用收入：10万港币以上",
                    "希望以年薪描述（于下方补充说明选填栏填写）",
                ],
            },
            {
                "id": "premium_afford_ratio_band",
                "input": "select",
                "options": [
                    "愿承担保费约占可动用收入：低于10%",
                    "10%-20%",
                    "21%-30%",
                    "31%-40%",
                    "41%-50%",
                    "高于50%",
                    "暂不确定",
                ],
            },
            {
                "id": "primary_goals",
                "input": "multiselect",
                "options": [
                    {"value": "death_disability", "label": "身故/意外/伤残保障"},
                    {"value": "medical_hospital", "label": "住院/医疗费用"},
                    {"value": "critical_illness", "label": "重大疾病一次性赔付"},
                    {"value": "wealth_savings", "label": "储蓄/财富增值"},
                    {"value": "retirement_income", "label": "退休现金流"},
                    {"value": "education_legacy", "label": "教育金/传承安排"},
                ],
            },
        ],
        "optional": [
            {"id": "existing_coverage_summary", "input": "textarea", "max_len": 800},
            {"id": "mortgage_debts_band", "input": "select", "options": ["无或极少", "50万港币以下", "50-200万", "200-500万", "500万以上", "暂不确定"]},
            {"id": "liquid_assets_band", "input": "select", "options": ["10万以下", "10-50万", "50-200万", "200-500万", "500万以上", "暂不确定"]},
            {"id": "smoking", "input": "select", "options": ["否", "是", "已戒烟"]},
            {"id": "health_notes", "input": "textarea", "max_len": 600},
            {"id": "education_funding_note", "input": "textarea", "max_len": 400},
            {"id": "target_retirement_age", "input": "text", "max_len": 32},
            {"id": "mpf_note", "input": "textarea", "max_len": 400},
            {"id": "currency_preference", "input": "select", "options": ["港币", "美元", "人民币", "多币种均可", "暂不确定"]},
            {"id": "existing_policies_free_text", "input": "textarea", "max_len": 1000},
        ],
    }

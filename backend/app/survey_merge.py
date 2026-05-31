"""Merge validated supplement survey answers into the latest profile snapshot."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProfileSnapshot
from app.survey_template import PRIMARY_GOAL_OPTIONS, _blankish

_GOAL_CN: dict[str, str] = {
    "death_disability": "身故/意外/伤残保障",
    "medical_hospital": "住院/医疗",
    "critical_illness": "重大疾病",
    "wealth_savings": "储蓄/财富增值",
    "retirement_income": "退休现金流",
    "education_legacy": "教育金/传承",
}


def _goals_text(answers: dict[str, Any]) -> str:
    g = answers.get("primary_goals")
    if not isinstance(g, list):
        return ""
    parts: list[str] = []
    for x in g:
        s = str(x).strip()
        if s in _GOAL_CN:
            parts.append(_GOAL_CN[s])
        elif s in PRIMARY_GOAL_OPTIONS:
            parts.append(_GOAL_CN.get(s, s))
    return "、".join(parts) if parts else ""


def _cats_from_goals(answers: dict[str, Any]) -> list[str]:
    g = answers.get("primary_goals")
    if not isinstance(g, list):
        return []
    cats: list[str] = []
    for x in g:
        s = str(x).strip()
        if s == "medical_hospital" and "医疗" not in cats:
            cats.append("医疗")
        if s == "death_disability" and "人寿" not in cats:
            cats.append("人寿")
        if s == "critical_illness" and "重疾" not in cats:
            cats.append("重疾")
        if s in ("wealth_savings", "retirement_income", "education_legacy"):
            if "储蓄" not in cats:
                cats.append("储蓄")
    return cats


def survey_to_dimension_strings(answers: dict[str, Any]) -> dict[str, str]:
    """Map survey to PROFILE dimensions keys."""
    life_parts = [
        answers.get("age_band"),
        f"常住/工作地：{answers.get('residency_region','')}".strip(),
        f"职业：{answers.get('occupation_category','')}".strip(),
    ]
    life_stage = "；".join(p for p in life_parts if p and not _blankish(p))

    fam_parts = [answers.get("marital_dependents_summary")]
    if not _blankish(answers.get("education_funding_note")):
        fam_parts.append(f"教育金关注：{answers.get('education_funding_note')}")
    family = "；".join(p for p in fam_parts if not _blankish(p))

    fin_parts = [
        answers.get("income_band"),
        answers.get("premium_afford_ratio_band"),
    ]
    for key, label in (
        ("mortgage_debts_band", "负债"),
        ("liquid_assets_band", "流动资产"),
        ("mpf_note", "强积金/供款"),
        ("currency_preference", "保单货币偏好"),
    ):
        v = answers.get(key)
        if not _blankish(v):
            fin_parts.append(f"{label}：{v}")
    finance = "；".join(p for p in fin_parts if not _blankish(p))

    h_parts = []
    if not _blankish(answers.get("smoking")):
        h_parts.append(f"吸烟：{answers.get('smoking')}")
    if not _blankish(answers.get("health_notes")):
        h_parts.append(answers.get("health_notes"))
    if not _blankish(answers.get("existing_coverage_summary")):
        h_parts.append(f"现有保障概述：{answers.get('existing_coverage_summary')}")
    health = "；".join(h_parts)

    goals = _goals_text(answers)
    if not goals and not _blankish(answers.get("education_funding_note")):
        goals = str(answers.get("education_funding_note"))
    elif not _blankish(answers.get("education_funding_note")):
        goals = f"{goals}（教育规划：{answers.get('education_funding_note')}）"

    risk = answers.get("premium_afford_ratio_band") or ""

    vals: list[str] = []
    if not _blankish(answers.get("currency_preference")):
        vals.append(f"偏好币种：{answers.get('currency_preference')}")
    g2 = _goals_text(answers)
    if g2:
        vals.append(f"目标侧重：{g2}")
    values = "；".join(vals)

    return {
        "life_stage": life_stage,
        "family": family,
        "finance": finance,
        "health": health,
        "goals": goals,
        "risk_appetite": f"保费承担意愿：{risk}" if not _blankish(risk) else "",
        "values": values,
    }


def _dim_mergeable(cur: Any) -> bool:
    if cur is None:
        return True
    if isinstance(cur, str):
        return _blankish(cur)
    return False


def merge_survey_into_profile_snapshot(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    answers: dict[str, Any],
) -> ProfileSnapshot:
    prev = db.scalar(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.conversation_id == conversation_id)
        .order_by(ProfileSnapshot.id.desc())
        .limit(1)
    )
    base_blob: dict[str, Any] = {}
    prev_summary = ""
    if prev:
        prev_summary = (prev.summary_text or "").strip()
        if isinstance(prev.structured_json, dict):
            base_blob = {**prev.structured_json}

    dim_old = base_blob.get("dimensions")
    if not isinstance(dim_old, dict):
        dim_old = {}
    dim_keys = (
        "finance",
        "family",
        "health",
        "goals",
        "risk_appetite",
        "life_stage",
        "values",
    )
    dims: dict[str, str] = {k: str(dim_old.get(k) or "").strip() for k in dim_keys}
    patch = survey_to_dimension_strings(answers)
    for k in dim_keys:
        nv = patch.get(k, "")
        if not nv.strip():
            continue
        if _dim_mergeable(dims.get(k)):
            dims[k] = nv

    base_blob["dimensions"] = dims

    km_old = base_blob.get("key_memories")
    km: list[str] = (
        [str(x).strip() for x in km_old if str(x).strip()]
        if isinstance(km_old, list)
        else []
    )
    for line in (
        f"调查表-年龄区间：{answers.get('age_band','')}",
        f"调查表-家庭责任：{answers.get('marital_dependents_summary','')}",
        f"调查表-核心目标：{_goals_text(answers)}",
    ):
        if not _blankish(line.split("：", 1)[-1]):
            if line not in km:
                km.append(line)

    base_blob["key_memories"] = km[:28]

    cats_old = base_blob.get("product_focus_categories")
    cats: list[str] = (
        [str(x).strip() for x in cats_old if str(x).strip()]
        if isinstance(cats_old, list)
        else []
    )
    for c in _cats_from_goals(answers):
        if c not in cats:
            cats.append(c)
    base_blob["product_focus_categories"] = cats

    bh = str(base_blob.get("budget_hint") or "").strip()
    budget_new = "；".join(
        x
        for x in (answers.get("income_band"), answers.get("premium_afford_ratio_band"))
        if not _blankish(x)
    )
    if _dim_mergeable(bh) and budget_new:
        base_blob["budget_hint"] = budget_new
    elif not _dim_mergeable(bh) and budget_new and bh != budget_new:
        base_blob["budget_hint"] = f"{bh}（调查表：{budget_new}）"

    summary_add = "（补充调查表已并入画像。）"
    new_summary = (prev_summary + summary_add).strip() if prev_summary else summary_add
    base_blob["summary_text"] = new_summary

    row = ProfileSnapshot(
        user_id=user_id,
        conversation_id=conversation_id,
        summary_text=new_summary,
        structured_json=base_blob,
    )
    db.add(row)
    return row

"""Infer report-supplement survey drafts from chat profile (fill blanks only)."""

from __future__ import annotations

import re
from typing import Any

from app.survey_template import (
    OPTIONAL_FIELDS,
    PRIMARY_GOAL_OPTIONS,
    REQUIRED_FIELDS,
    _blankish,
    coerce_survey_answers,
)

_AGE_BANDS = (
    "18以下",
    "18-24",
    "25-34",
    "35-44",
    "45-54",
    "55-64",
    "65及以上",
)

_INCOME_OPTIONS = (
    "每月可动用收入：1万港币以下",
    "每月可动用收入：1万-2万港币",
    "每月可动用收入：2万-5万港币",
    "每月可动用收入：5万-10万港币",
    "每月可动用收入：10万港币以上",
)

_PREMIUM_OPTIONS = (
    "愿承担保费约占可动用收入：低于10%",
    "10%-20%",
    "21%-30%",
    "31%-40%",
    "41%-50%",
    "高于50%",
    "暂不确定",
)


def _corpus(
    summary_text: str,
    structured: dict[str, Any] | None,
    user_messages: list[str] | None,
) -> str:
    parts: list[str] = [summary_text or ""]
    if isinstance(structured, dict):
        parts.append(str(structured.get("summary_text") or ""))
        dims = structured.get("dimensions")
        if isinstance(dims, dict):
            parts.extend(str(v) for v in dims.values() if v)
        kms = structured.get("key_memories")
        if isinstance(kms, list):
            parts.extend(str(x) for x in kms if x)
        parts.append(str(structured.get("budget_hint") or ""))
        cats = structured.get("product_focus_categories")
        if isinstance(cats, list):
            parts.extend(str(x) for x in cats)
    if user_messages:
        parts.extend(user_messages)
    return "\n".join(parts)


def _age_to_band(age: int) -> str:
    if age < 18:
        return "18以下"
    if age <= 24:
        return "18-24"
    if age <= 34:
        return "25-34"
    if age <= 44:
        return "35-44"
    if age <= 54:
        return "45-54"
    if age <= 64:
        return "55-64"
    return "65及以上"


def _pick_age_band(text: str) -> str:
    m = re.search(r"调查表-年龄区间[：:]\s*(18以下|18-24|25-34|35-44|45-54|55-64|65及以上)", text)
    if m:
        return m.group(1)
    for band in _AGE_BANDS:
        if band in text and band != "18以下":
            # Prefer explicit band tokens like 18-24 over incidental digits
            if re.search(rf"(?<!\d){re.escape(band)}(?!\d)", text):
                return band
    m2 = re.search(r"(\d{1,2})\s*岁", text)
    if m2:
        return _age_to_band(int(m2.group(1)))
    m3 = re.search(
        r"(?i)(?:i'?m|i am|age(?:d)?|year[- ]old(?:\s+male|\s+female)?)\D{0,12}(\d{1,2})"
        r"|(\d{1,2})\s*[- ]?year(?:s)?[- ]old",
        text,
    )
    if m3:
        age = int(m3.group(1) or m3.group(2))
        return _age_to_band(age)
    return ""


def _pick_residency(text: str) -> str:
    if re.search(r"(?i)hong\s*kong|基于香港|香港|留港|在港", text):
        return "香港"
    if re.search(r"(?i)mainland\s*china|中国内地|内地|大陆", text):
        return "中国内地"
    if re.search(r"(?i)\bmacao\b|\bmacau\b|澳门", text):
        return "澳门"
    if re.search(r"(?i)\btaiwan\b|台湾", text):
        return "台湾"
    return ""


def _pick_marital(text: str) -> str:
    m = re.search(r"调查表-家庭责任[：:]\s*([^\n；;]+)", text)
    if m:
        return m.group(1).strip()[:500]
    if re.search(r"(?i)\bsingle\b|单身|未婚", text):
        return "单身"
    if re.search(r"(?i)\bmarried\b|已婚", text):
        return "已婚"
    return ""


def _pick_occupation(text: str) -> str:
    if re.search(r"(?i)student|between\s+jobs|unemployed|学生|待业|在读", text):
        return "学生/待业"
    if re.search(r"(?i)office\s+employee|雇员（办公室）|办公室|文职", text):
        return "雇员（办公室）"
    if re.search(r"(?i)manual|outdoor|field\s*work|体力|外勤", text):
        return "雇员（需体力劳动或外勤）"
    if re.search(r"(?i)self[- ]employed|professional|自雇|专业人士", text):
        return "专业人士/自雇"
    if re.search(r"(?i)business\s+owner|shareholder|企业主|股东", text):
        return "企业主或股东"
    if re.search(r"(?i)\bretired\b|退休", text):
        return "退休"
    return ""


def _pick_income(text: str) -> str:
    for opt in _INCOME_OPTIONS:
        if opt in text:
            return opt
    if re.search(
        r"(?i)HKD\s*10\s*k?\s*[-–~to]+\s*20\s*k|10,?000\s*[-–~to]+\s*20,?000|"
        r"1万-2万|1–2万|10000.?20000|1万至2万",
        text,
    ):
        return "每月可动用收入：1万-2万港币"
    if re.search(r"(?i)HKD\s*20\s*k?\s*[-–~to]+\s*50\s*k|2万-5万|2–5万", text):
        return "每月可动用收入：2万-5万港币"
    if re.search(r"(?i)HKD\s*50\s*k?\s*[-–~to]+\s*100\s*k|5万-10万|5–10万", text):
        return "每月可动用收入：5万-10万港币"
    if re.search(r"(?i)over\s*HKD\s*100\s*k|10万港币以上|10万以上", text):
        return "每月可动用收入：10万港币以上"
    if re.search(r"(?i)under\s*HKD\s*10\s*k|1万港币以下|一万以下", text):
        return "每月可动用收入：1万港币以下"
    # Budget 1000-4000/mo with 10-20% implies ~10k-20k disposable
    if re.search(
        r"(?i)HKD\s*1,?000\s*[-–~to]+\s*4,?000|1000\s*[-–~到至]\s*4000|每月约?1000",
        text,
    ) and re.search(r"10%\s*[-–~到至]?\s*20%|10%-20%", text):
        return "每月可动用收入：1万-2万港币"
    return ""


def _pick_premium_ratio(text: str) -> str:
    for opt in _PREMIUM_OPTIONS:
        if opt in text:
            return opt
    if re.search(r"10%\s*[-–~到至]?\s*20%|10%-20%", text):
        return "10%-20%"
    if re.search(r"(?i)under\s*10%|低于\s*10%|不到\s*10%|< ?10%", text):
        return "愿承担保费约占可动用收入：低于10%"
    if re.search(r"21%\s*[-–~到至]?\s*30%|21%-30%", text):
        return "21%-30%"
    return ""


def _pick_goals(text: str, structured: dict[str, Any] | None) -> list[str]:
    goals: list[str] = []

    def add(g: str) -> None:
        if g in PRIMARY_GOAL_OPTIONS and g not in goals:
            goals.append(g)

    if isinstance(structured, dict):
        cats = structured.get("product_focus_categories")
        if isinstance(cats, list):
            for c in cats:
                s = str(c)
                if re.search(r"(?i)medical|hospital|医疗|住院", s):
                    add("medical_hospital")
                if re.search(r"(?i)critical|重疾", s):
                    add("critical_illness")
                if re.search(r"(?i)life\b|death|人寿|身故", s):
                    add("death_disability")
                if re.search(r"(?i)saving|wealth|储蓄", s):
                    add("wealth_savings")

    if re.search(r"(?i)hospital\s*(medical|cover|plan)?|medical\s*(cover|plan|insurance)|住院|医疗险|医疗费用|医疗保障", text):
        add("medical_hospital")
    if re.search(r"(?i)critical\s*illness|CI\b|重疾|重大疾病|大病", text):
        add("critical_illness")
    if re.search(r"(?i)death|accident|disability|life\s*cover|身故|意外|伤残|人寿", text):
        add("death_disability")
    if re.search(r"(?i)savings?|wealth|储蓄|财富增值", text):
        add("wealth_savings")
    if re.search(r"(?i)retirement|退休", text):
        add("retirement_income")
    if re.search(r"(?i)education|legacy|教育金|传承", text):
        add("education_legacy")

    # Explicit survey memory line
    m = re.search(r"调查表-核心目标[：:]([^\n]+)", text)
    if m:
        blob = m.group(1)
        if "住院" in blob or "医疗" in blob:
            add("medical_hospital")
        if "重大疾病" in blob or "重疾" in blob:
            add("critical_illness")
        if "身故" in blob or "意外" in blob or "伤残" in blob:
            add("death_disability")

    return goals


def _pick_smoking(text: str) -> str:
    if re.search(r"(?i)non[- ]?smoker|never\s+smok|从不吸烟|不吸烟|非吸烟|从不抽烟", text):
        return "否"
    if re.search(r"(?i)former\s+smoker|quit\s+smok|已戒烟", text):
        return "已戒烟"
    if re.search(r"(?i)\bsmoker\b|吸烟|抽烟", text) and not re.search(
        r"(?i)non|never|不吸烟|从不", text
    ):
        return "是"
    return ""


def _pick_health_notes(text: str) -> str:
    if re.search(
        r"(?i)very\s+healthy|no\s+(known\s+)?(medical|health)\s+(issues|history)|"
        r"非常健康|很健康|身体健康|无既往|没有病史",
        text,
    ):
        return "非常健康，无既往病史或长期服药"
    return ""


def _pick_existing_coverage(text: str) -> str:
    if re.search(
        r"(?i)never\s+bought\s+any\s+insurance|no\s+(personal\s+)?insurance|"
        r"haven'?t\s+bought\s+any\s+insurance|没有买过任何保险|暂无.*保险|"
        r"目前没有.*保险|没有任何保险|无在保",
        text,
    ):
        return "暂无个人在保商业保险"
    return ""


def infer_survey_draft_from_chat(
    *,
    summary_text: str = "",
    structured: dict[str, Any] | None = None,
    user_messages: list[str] | None = None,
) -> dict[str, Any]:
    """Best-effort survey draft from chat profile; values are template-canonical Chinese enums."""
    text = _corpus(summary_text, structured, user_messages)
    raw: dict[str, Any] = {k: "" for k in REQUIRED_FIELDS + OPTIONAL_FIELDS}
    raw["primary_goals"] = []

    raw["age_band"] = _pick_age_band(text)
    raw["residency_region"] = _pick_residency(text)
    raw["marital_dependents_summary"] = _pick_marital(text)
    raw["occupation_category"] = _pick_occupation(text)
    raw["income_band"] = _pick_income(text)
    raw["premium_afford_ratio_band"] = _pick_premium_ratio(text)
    raw["primary_goals"] = _pick_goals(text, structured)
    raw["smoking"] = _pick_smoking(text)
    raw["health_notes"] = _pick_health_notes(text)
    raw["existing_coverage_summary"] = _pick_existing_coverage(text)

    # Soft occupation default for young student-like profiles when age known but job blank
    if not raw["occupation_category"] and raw["age_band"] in ("18以下", "18-24"):
        if re.search(r"(?i)student|between\s+jobs|学生|待业|规划初期|年轻", text):
            raw["occupation_category"] = "学生/待业"

    return coerce_survey_answers(raw)


def merge_survey_fill_blanks_only(
    existing: dict[str, Any] | None,
    inferred: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep non-blank existing answers; fill only empty slots from inferred."""
    base = coerce_survey_answers(existing)
    draft = coerce_survey_answers(inferred)
    out = dict(base)

    for key in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        if key == "primary_goals":
            cur = out.get("primary_goals")
            if isinstance(cur, list) and len(cur) > 0:
                continue
            inf = draft.get("primary_goals")
            if isinstance(inf, list) and inf:
                out["primary_goals"] = list(inf)
            continue
        if not _blankish(out.get(key)) and str(out.get(key) or "").strip():
            continue
        cand = draft.get(key)
        if not _blankish(cand):
            out[key] = cand

    return coerce_survey_answers(out)

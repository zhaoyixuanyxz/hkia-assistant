"""Merge dialogue profile + validated survey into one structured blob and fused prose for report/RAG."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import HTTPException

from app.llm import LLMService
from app.prompts import PROFILE_DUAL_SOURCE_FUSE_MARKER, profile_dual_source_fuse_system
from app.survey_merge import _cats_from_goals, _goals_text, survey_to_dimension_strings
from app.survey_template import _blankish

logger = logging.getLogger(__name__)

DIM_KEYS = (
    "finance",
    "family",
    "health",
    "goals",
    "risk_appetite",
    "life_stage",
    "values",
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip())


def merge_dimension_pair(conv: str, survey: str) -> str:
    a, b = (conv or "").strip(), (survey or "").strip()
    if not a:
        return b
    if not b:
        return a
    if b in a or _norm(b) in _norm(a):
        return a
    if a in b or _norm(a) in _norm(b):
        return b
    return f"{a}；{b}"


def merge_structured_dual_source(
    structured: dict[str, Any] | None, survey_answers: dict[str, Any]
) -> dict[str, Any]:
    survey_dims = survey_to_dimension_strings(survey_answers)
    base: dict[str, Any] = dict(structured) if isinstance(structured, dict) else {}
    dim_old = base.get("dimensions")
    old: dict[str, str] = {}
    if isinstance(dim_old, dict):
        old = {k: str(dim_old.get(k) or "").strip() for k in DIM_KEYS}
    new_dims = {
        k: merge_dimension_pair(old.get(k, ""), str(survey_dims.get(k) or ""))
        for k in DIM_KEYS
    }
    base["dimensions"] = new_dims

    cats: list[str] = []
    old_cats_raw = base.get("product_focus_categories")
    if isinstance(old_cats_raw, list):
        cats = [str(x).strip() for x in old_cats_raw if str(x).strip()]
    for c in _cats_from_goals(survey_answers):
        if c not in cats:
            cats.append(c)
    base["product_focus_categories"] = cats

    bh_old = str(base.get("budget_hint") or "").strip()
    bh_survey_parts = [
        str(x).strip()
        for x in (survey_answers.get("income_band"), survey_answers.get("premium_afford_ratio_band"))
        if not _blankish(x)
    ]
    bh_survey = "；".join(bh_survey_parts)
    if bh_survey and bh_old:
        base["budget_hint"] = merge_dimension_pair(bh_old, bh_survey)
    elif bh_survey:
        base["budget_hint"] = bh_survey
    elif bh_old:
        base["budget_hint"] = bh_old

    km: list[str] = []
    km_old = base.get("key_memories")
    if isinstance(km_old, list):
        km = [str(x).strip() for x in km_old if str(x).strip()]
    anchors = (
        f"[调查表]年龄区间：{survey_answers.get('age_band', '')}",
        f"[调查表]核心目标：{_goals_text(survey_answers)}",
        f"[调查表]婚姻与供养责任：{survey_answers.get('marital_dependents_summary', '')}",
    )
    for line in anchors:
        tail = line.split("：", 1)[-1].strip()
        if tail and tail not in ("不清楚", "—", "-"):
            if line.strip() not in km:
                km.append(line.strip())
    base["key_memories"] = km[:28]

    base["profile_dual_source_integrated_at"] = "report_generate"
    base["dual_source_marker"] = PROFILE_DUAL_SOURCE_FUSE_MARKER
    return base


def _struct_dims_readable(merged_struct: dict[str, Any]) -> str:
    dims = merged_struct.get("dimensions") if isinstance(merged_struct.get("dimensions"), dict) else {}
    lines: list[str] = []
    labels = (
        ("life_stage", "人生阶段/年龄与职业"),
        ("family", "家庭与责任"),
        ("finance", "财务与预算"),
        ("health", "健康与生活习惯"),
        ("goals", "保障与财富目标"),
        ("risk_appetite", "风险与保费承受能力"),
        ("values", "偏好与价值取向"),
    )
    for key, lab in labels:
        v = str(dims.get(key) or "").strip()
        if v:
            lines.append(f"- {lab}：{v}")
    cats = merged_struct.get("product_focus_categories")
    if isinstance(cats, list) and cats:
        lines.append(f"- 意向产品大类：{'、'.join(str(x) for x in cats if x)}")
    bh = str(merged_struct.get("budget_hint") or "").strip()
    if bh:
        lines.append(f"- 预算与收入线索：{bh}")
    return "\n".join(lines) if lines else "（合并后结构化维度暂无有效文本）"


def rule_based_integrated_summary(
    conversation_summary: str,
    merged_struct: dict[str, Any],
    survey_block: str,
) -> str:
    parts: list[str] = [
        "【融合画像·系统兜底】已将「会话对话侧的画像摘要 / 结构化 JSON」"
        "与「补充调查表」做字段级合并（见下方结构化条目）。"
        "以下分段列出两路原材料，请在阅读时自行去重；正式报告请以本节与结构化 JSON 一致为准。"
    ]
    if conversation_summary.strip():
        parts.append("一、对话侧画像摘要：\n" + conversation_summary.strip())
    parts.append("二、合并后的结构化维度（对话 + 调查表）：\n" + _struct_dims_readable(merged_struct))
    if survey_block.strip():
        parts.append(
            "三、调查表原始摘录（仅存于表中、尚未反映进维度的核对用）：\n"
            + survey_block.strip()[:4500]
        )
    return "\n\n".join(parts)


def _parse_integrated_json(raw: str) -> str | None:
    text = (raw or "").strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)```$", text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    summ = data.get("integrated_summary")
    if isinstance(summ, str) and len(summ.strip()) >= 40:
        return summ.strip()
    return None


def fuse_profile_summary_dual_source(
    llm: LLMService,
    *,
    conversation_summary: str,
    merged_struct: dict[str, Any],
    survey_block: str,
    locale: str | None = None,
) -> tuple[str, str]:
    struct_dump = json.dumps(merged_struct, ensure_ascii=False)[:14000]
    user = (
        "【对话画像摘要】（可能为空；仍可能有调查表未能覆盖的对话事实）\n"
        f"{conversation_summary.strip() or '（暂无）'}\n\n"
        f"【会话结构化 JSON · 已与调查表按维度合并】\n{struct_dump}\n\n"
        "【补充调查表摘录】（与上文重复的请在输出中去重表述）\n"
        f"{survey_block.strip() or '（无）'}\n\n"
        '只输出 JSON：`{"integrated_summary":"..."}` 单键对象。'
    )
    try:
        raw = llm.complete_json_text(
            user, profile_dual_source_fuse_system(locale), thinking=True
        )
        fused = _parse_integrated_json(raw)
        if fused:
            return fused, "llm_dual_source_fuse"
    except HTTPException as e:
        logger.warning("dual_source_profile_fuse_http detail=%s", getattr(e, "detail", e))
    except Exception:
        logger.exception("dual_source_profile_fuse_failed")
    fb = rule_based_integrated_summary(conversation_summary, merged_struct, survey_block)
    return fb, "rule_fallback"


def build_integrated_profile_for_report(
    llm: LLMService,
    *,
    conversation_profile_summary: str,
    conversation_structured: dict[str, Any] | None,
    survey_answers: dict[str, Any],
    survey_block: str,
    locale: str | None = None,
) -> tuple[str, dict[str, Any], str]:
    merged = merge_structured_dual_source(conversation_structured, survey_answers)
    summary, fuse_mode = fuse_profile_summary_dual_source(
        llm,
        conversation_summary=conversation_profile_summary,
        merged_struct=merged,
        survey_block=survey_block,
        locale=locale,
    )
    return summary, merged, fuse_mode
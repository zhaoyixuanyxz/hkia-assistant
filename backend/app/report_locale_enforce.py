"""Force report user-facing strings to follow UI locale when the model drifts to Chinese."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.locale_support import normalize_locale, output_language_instruction
from app.report_survey_overlay import (
    synthesized_insights_from_survey,
    synthesized_user_background_from_survey,
)
from app.schemas import ReportPayload, ReportProductPick
from app.survey_template import localize_primary_goal

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_DEFAULT_TITLE = {
    "zh-CN": "中国人寿海外保险配置参考报告",
    "zh-TW": "中國人壽海外保險配置參考報告",
    "en": "China Life Overseas planning reference report",
}

_COMMON_CHART_LABEL_EN: dict[str, str] = {
    "医疗": "Medical",
    "醫療": "Medical",
    "重疾": "Critical illness",
    "危疾": "Critical illness",
    "寿险": "Life",
    "壽險": "Life",
    "储蓄": "Savings",
    "儲蓄": "Savings",
    "保障": "Protection",
    "保障优先级": "Protection priority",
    "保障優先級": "Protection priority",
}


def _english_chart_label(name: str, index: int) -> str:
    s = (name or "").strip()
    if s in _COMMON_CHART_LABEL_EN:
        return _COMMON_CHART_LABEL_EN[s]
    for zh, en in _COMMON_CHART_LABEL_EN.items():
        if zh in s and len(s) <= 16:
            return en
    return f"Item {index + 1}"


def field_needs_target_language_rewrite(text: str, locale: str | None = None) -> bool:
    """True when locale=en (or zh-TW) but the string is still substantially Chinese."""
    loc = normalize_locale(locale)
    if loc == "zh-CN":
        return False
    s = text or ""
    n = len(_CJK_RE.findall(s))
    if loc == "en":
        if n >= 4:
            return True
        # Short Chinese labels such as「医疗」「重疾」
        if n >= 2 and len(s.strip()) <= 24:
            return True
        return False
    # zh-TW: only rewrite when output is clearly simplified-heavy mixed with SC markers —
    # for now treat same as "too much SC-looking CJK in an EN check" is not needed;
    # rewrite when model left simplified boilerplate phrases is handled elsewhere.
    return False


def report_payload_needs_locale_rewrite(
    payload: ReportPayload, locale: str | None = None
) -> bool:
    loc = normalize_locale(locale)
    if loc != "en":
        return False
    chunks: list[str] = [
        payload.title or "",
        payload.user_background or "",
        payload.insights or "",
        payload.allocation_direction or "",
        payload.product_category_suggestions or "",
        payload.risk_notes or "",
        payload.limited_data_notice or "",
        " ".join(payload.follow_up_questions or []),
    ]
    for pick in payload.concrete_product_picks or []:
        chunks.append(pick.rationale or "")
    for chart in payload.charts or []:
        if hasattr(chart, "model_dump"):
            chart_d = chart.model_dump()
        elif isinstance(chart, dict):
            chart_d = chart
        else:
            continue
        chunks.append(str(chart_d.get("title") or ""))
        data = chart_d.get("data")
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    chunks.append(str(row.get("name") or ""))
    return any(field_needs_target_language_rewrite(c, loc) for c in chunks)


def synthesized_categories_from_survey(
    answers: dict[str, Any], locale: str | None = None
) -> str:
    loc = normalize_locale(locale)
    raw = answers.get("primary_goals")
    if not isinstance(raw, list) or not raw:
        return {
            "en": "Protection categories to confirm with a licensed adviser",
            "zh-TW": "請與持牌顧問確認之保障類別",
            "zh-CN": "请与持牌顾问确认之保障类别",
        }[loc]
    labels = [localize_primary_goal(str(x), loc) for x in raw if str(x).strip()]
    joiner = ", " if loc == "en" else "、"
    return joiner.join(labels)


def synthesized_allocation_from_survey(
    answers: dict[str, Any], locale: str | None = None
) -> str:
    loc = normalize_locale(locale)
    cats = synthesized_categories_from_survey(answers, loc)
    if loc == "en":
        return (
            f"Prioritise building a protection stack aligned with: {cats}. "
            "Treat sum assured, waiting periods, and exclusions as subject to formal "
            "illustrations and underwriting; this is directional planning only."
        )
    if loc == "zh-TW":
        return (
            f"建議優先圍繞以下方向建立保障組合：{cats}。"
            "保額、等候期與除外責任均須以正式計劃書與核保結論為準；本文僅作方向性規劃參考。"
        )
    return (
        f"建议优先围绕以下方向建立保障组合：{cats}。"
        "保额、等候期与除外责任均须以正式计划书与核保结论为准；本文仅作方向性规划参考。"
    )


def synthesized_risk_notes(locale: str | None = None) -> str:
    loc = normalize_locale(locale)
    return {
        "en": (
            "Product terms, fees, benefits, and suitability are subject to insurer documents "
            "and licensed advice. Do not treat this report as a purchase recommendation."
        ),
        "zh-TW": (
            "產品條款、費用、利益與適合性均以保險公司文件及持牌意見為準。"
            "請勿將本報告視為購買建議。"
        ),
        "zh-CN": (
            "产品条款、费用、利益与适合性均以保险公司文件及持牌意见为准。"
            "请勿将本报告视为购买建议。"
        ),
    }[loc]


def synthesized_limited_data_notice(locale: str | None = None) -> str:
    loc = normalize_locale(locale)
    return {
        "en": (
            "Analysis uses the session profile, supplement form, and a limited public product "
            "library via retrieval. It is not a complete catalogue and is for general reference only."
        ),
        "zh-TW": (
            "分析基於本輪對話、補充調查表，以及經檢索的有限公開產品資料庫；"
            "並非完整產品目錄，僅供一般參考。"
        ),
        "zh-CN": (
            "分析基于本轮对话、补充调查表，以及经检索的有限公开产品资料库；"
            "并非完整产品目录，仅供一般参考。"
        ),
    }[loc]


def _english_rationale_stub(name: str) -> str:
    label = (name or "").strip() or "this plan"
    return (
        f"{label} is cited from the retrieved China Life Overseas public library as an "
        "illustrative cover-line reference. Confirm terms, waiting periods, and suitability "
        "with a licensed adviser before any application."
    )


def force_survey_derived_fields_to_locale(
    payload: ReportPayload,
    answers: dict[str, Any],
    locale: str | None = None,
) -> ReportPayload:
    """Deterministically rewrite key prose when locale=en and Chinese remains."""
    loc = normalize_locale(locale)
    if loc != "en":
        return payload

    updates: dict[str, Any] = {}
    if field_needs_target_language_rewrite(payload.title or "", loc):
        updates["title"] = _DEFAULT_TITLE[loc]
    if field_needs_target_language_rewrite(payload.user_background or "", loc):
        updates["user_background"] = synthesized_user_background_from_survey(answers, loc)
    if field_needs_target_language_rewrite(payload.insights or "", loc):
        updates["insights"] = synthesized_insights_from_survey(answers, loc)
    if field_needs_target_language_rewrite(payload.allocation_direction or "", loc):
        updates["allocation_direction"] = synthesized_allocation_from_survey(answers, loc)
    if field_needs_target_language_rewrite(
        payload.product_category_suggestions or "", loc
    ):
        updates["product_category_suggestions"] = synthesized_categories_from_survey(
            answers, loc
        )
    if field_needs_target_language_rewrite(payload.risk_notes or "", loc):
        updates["risk_notes"] = synthesized_risk_notes(loc)
    if field_needs_target_language_rewrite(payload.limited_data_notice or "", loc):
        updates["limited_data_notice"] = synthesized_limited_data_notice(loc)

    if any(
        field_needs_target_language_rewrite(q, loc)
        for q in (payload.follow_up_questions or [])
    ):
        updates["follow_up_questions"] = []

    picks = list(payload.concrete_product_picks or [])
    new_picks: list[ReportProductPick] = []
    picks_changed = False
    for pick in picks:
        if field_needs_target_language_rewrite(pick.rationale or "", loc):
            new_picks.append(
                pick.model_copy(update={"rationale": _english_rationale_stub(pick.name)})
            )
            picks_changed = True
        else:
            new_picks.append(pick)
    if picks_changed:
        updates["concrete_product_picks"] = new_picks

    charts = list(payload.charts or [])
    new_charts: list[Any] = []
    charts_changed = False
    for chart in charts:
        if hasattr(chart, "model_dump"):
            c = chart.model_dump()
        elif isinstance(chart, dict):
            c = dict(chart)
        else:
            new_charts.append(chart)
            continue
        if field_needs_target_language_rewrite(str(c.get("title") or ""), loc):
            title = str(c.get("title") or "").strip()
            c["title"] = _COMMON_CHART_LABEL_EN.get(title, "Planning illustration")
            charts_changed = True
        data = c.get("data")
        if isinstance(data, list):
            rows: list[Any] = []
            for i, row in enumerate(data):
                if not isinstance(row, dict):
                    rows.append(row)
                    continue
                r = dict(row)
                name = str(r.get("name") or "")
                if field_needs_target_language_rewrite(name, loc):
                    r["name"] = _english_chart_label(name, i)
                    charts_changed = True
                rows.append(r)
            c["data"] = rows
        new_charts.append(c)
    if charts_changed:
        updates["charts"] = new_charts

    if not updates:
        return payload
    return payload.model_copy(update=updates)


def _rewrite_system(locale: str) -> str:
    return (
        "You rewrite insurance planning report JSON string values into the target locale. "
        "Return ONLY one JSON object with the same keys you were given. "
        "Keep product_id and source_url unchanged. Keep official product/plan names as provided "
        "(do not invent English formal policy titles). "
        f"{output_language_instruction(locale)}"
    )


def llm_rewrite_report_locale(
    llm: Any,
    payload: ReportPayload,
    locale: str | None = None,
) -> ReportPayload:
    """Best-effort LLM rewrite for remaining off-locale strings; falls back to input on failure."""
    loc = normalize_locale(locale)
    if loc != "en" or not report_payload_needs_locale_rewrite(payload, loc):
        return payload

    slim: dict[str, Any] = {
        "title": payload.title,
        "user_background": payload.user_background,
        "insights": payload.insights,
        "allocation_direction": payload.allocation_direction,
        "product_category_suggestions": payload.product_category_suggestions,
        "risk_notes": payload.risk_notes,
        "limited_data_notice": payload.limited_data_notice,
        "follow_up_questions": list(payload.follow_up_questions or []),
        "concrete_product_picks": [
            {
                "product_id": p.product_id,
                "name": p.name,
                "rationale": p.rationale,
                "source_url": p.source_url,
            }
            for p in (payload.concrete_product_picks or [])
        ],
        "charts": payload.charts or [],
    }
    try:
        raw = llm.complete_json_text(
            "Rewrite every user-facing string value into professional English. "
            "Chart titles and each charts[].data[].name must be English. "
            "Official product names may stay as in the input.\n\n"
            + json.dumps(slim, ensure_ascii=False),
            _rewrite_system(loc),
            thinking=False,
        )
        from app.llm import parse_report_json

        rewritten = parse_report_json(raw)
        # Preserve disclaimer from original; merge_report_disclaimer runs later.
        return rewritten.model_copy(
            update={
                "disclaimer": payload.disclaimer,
            }
        )
    except Exception:
        logger.exception("llm_rewrite_report_locale_failed")
        return payload


def enforce_report_output_locale(
    payload: ReportPayload,
    answers: dict[str, Any],
    locale: str | None = None,
    llm: Any | None = None,
) -> ReportPayload:
    """
    Ensure EN reports are English even when the architect model drifts to Chinese.

    Order: deterministic survey-backed rewrite → optional LLM polish if CJK remains.
    """
    loc = normalize_locale(locale)
    if loc == "zh-CN":
        return payload

    from app.report_survey_overlay import overlay_report_when_model_ignores_survey

    payload = overlay_report_when_model_ignores_survey(payload, answers, locale=loc)
    payload = force_survey_derived_fields_to_locale(payload, answers, locale=loc)

    if llm is not None and report_payload_needs_locale_rewrite(payload, loc):
        polished = llm_rewrite_report_locale(llm, payload, locale=loc)
        # Deterministic pass again in case polish left CJK or emptied required fields.
        payload = force_survey_derived_fields_to_locale(polished, answers, locale=loc)

    return payload

"""When the LLM ignores validated survey facts, coerce report prose from structured answers."""

from __future__ import annotations

import re
from typing import Any

from app.schemas import ReportPayload
from app.survey_template import OPTIONAL_FIELDS, _blankish

_PRIMARY_GOALS_CN: dict[str, str] = {
    "death_disability": "身故与意外伤残类保障",
    "medical_hospital": "住院与医疗费用保障",
    "critical_illness": "重大疾病一次性给付",
    "wealth_savings": "储蓄与财富增值",
    "retirement_income": "退休后现金流安排",
    "education_legacy": "子女教育或传承安排",
}


def _goals_readable(answers: dict[str, Any]) -> str:
    raw = answers.get("primary_goals")
    if not isinstance(raw, list):
        return ""
    parts: list[str] = []
    for x in raw:
        s = str(x).strip()
        if not s:
            continue
        cn = _PRIMARY_GOALS_CN.get(s, s)
        if cn not in parts:
            parts.append(cn)
    return "、".join(parts)


def synthesized_user_background_from_survey(answers: dict[str, Any]) -> str:
    gtxt = _goals_readable(answers)
    blk1 = (
        "根据用户在本对话「补充调查表」中已保存并通过校验的资料，本节归纳其本人填写、可供配置参考的自述要点。"
        "（若报告其他段落与问卷表述不一致，以问卷勾选与条文为准。）"
    )
    lines_core = [
        f"年龄区间自述为「{answers.get('age_band', '')}」；常住/工作地归类为「{answers.get('residency_region', '')}」。",
        f"婚姻与家庭供养／责任概要：{answers.get('marital_dependents_summary', '')}。",
        f"职业类别：「{answers.get('occupation_category', '')}」。",
        (
            "申报的可动用收入水平与保费占收入的承受能力依次为："
            f"「{answers.get('income_band', '')}」"
            f"与「{answers.get('premium_afford_ratio_band', '')}」。"
        ),
        f"勾选的核心投保目标侧重：{gtxt or '（未解析到勾选）'}。",
    ]

    extras: list[str] = []
    for key, title in (
        ("existing_coverage_summary", "现有寿险/重疾/医疗保障概述"),
        ("mortgage_debts_band", "按揭与其他负债档位"),
        ("liquid_assets_band", "流动资金档位"),
        ("smoking", "吸烟状况"),
        ("health_notes", "健康状况补充"),
        ("education_funding_note", "教育金关注点"),
        ("target_retirement_age", "目标退休年龄"),
        ("mpf_note", "强积金或供款线索"),
        ("currency_preference", "保单货币偏好"),
        ("existing_policies_free_text", "已有保单补充说明"),
    ):
        if key not in OPTIONAL_FIELDS:
            continue
        v = answers.get(key)
        if not _blankish(v):
            extras.append(f"- {title}：{v}")

    blk2 = "\n".join(lines_core)
    if extras:
        blk2 += "\n\n用户补充（选填项）：\n" + "\n".join(extras)
    return f"{blk1}\n\n{blk2}"


def synthesized_insights_from_survey(answers: dict[str, Any]) -> str:
    gtxt = _goals_readable(answers)
    inc = answers.get("income_band", "")
    prem = answers.get("premium_afford_ratio_band", "")
    return (
        f"结合用户勾选的核心投保目标侧重（{gtxt}），可把后续配置讨论聚焦于与上述目标相一致的责任结构与产品大类；"
        f"其所申报的收入区间「{inc}」与保费承受能力「{prem}」可作为保额档次、年期与产品结构（例如保障优先或适度储蓄配比）讨论的约束。"
        "具体可执行投保方案仍须在香港持牌经纪人/顾问协助下、以正式计划书与承保结论为准。"
    )


def _boilerplate_conflicts_completed_survey(
    prose: str, answers: dict[str, Any]
) -> bool:
    """Report generation only runs after required survey passes validation.
    Replace boilerplate that still claims missing core fields already on file."""
    t = (prose or "").strip()
    if not t:
        return True

    def _filled(key: str) -> bool:
        v = answers.get(key)
        if key == "primary_goals":
            return isinstance(v, list) and len(v) > 0
        return isinstance(v, str) and not _blankish(v)

    # Typical bad output: 「用户背景信息暂未提供，请补充年龄、收入…」
    if re.search(
        r"(?:用户)?(?:个人)?背景(?:信息)?[\s，,。.]{0,8}(?:尚未|暂未|暂无)(?:提供|录入|披露|写明)?",
        t,
    ):
        return True
    if re.search(
        r"(?:尚未|暂未|暂无).{0,10}(?:详尽|足够|完整)?(?:的)?.{0,8}(?:用户|个人)?(?:背景|基本资料|信息)(?:[，,。.]|$)",
        t,
    ):
        return True

    # Model lists补充项 that validated survey already contains
    if _filled("age_band") and re.search(
        r"(?:请|敬请|建议|需要).{0,24}(?:补充|填写|说明|核实).{0,12}年龄",
        t,
    ):
        return True
    if _filled("income_band") and re.search(
        r"(?:补充|填写|说明|核实).{0,20}(?:收入|可动用|月薪|收支|每月)",
        t,
    ):
        return True
    if _filled("marital_dependents_summary") and re.search(
        r"(?:补充|填写|说明).{0,20}(?:家庭状况|婚姻|供养|扶养|赡养)",
        t,
    ):
        return True
    if _filled("primary_goals") and re.search(
        r"(?:补充|填写|说明|明确).{0,20}(?:保障目标|投保目标|核心目标)",
        t,
    ):
        return True

    return False


def _text_denies_known_survey_prose(s: str) -> bool:
    t = (s or "").strip()
    if len(t) < 28:
        return True
    patterns = (
        r"未提供(?:详细|充分|具体)?.{0,12}(?:个人|用户)?.{0,8}(?:背景|资料|信息)",
        r"(?:用户|个人)?背景(?:信息)?[\s\S]{0,14}(?:尚未|暂未|暂无)(?:提供|录入)?",
        r"暂无.{0,8}(?:详尽|详细|足够)?(?:的)?.{0,6}(?:个人|用户)?(?:背景|具体信息)",
        r"目前没有?.{0,10}(?:详尽|详细|足够)?(?:的)?.{0,8}(?:个人|用户)?(?:背景|资料|信息)",
        r"缺乏.{0,20}(?:具体|可用)?.{0,10}(?:用户|个人信息)",
        r"尚无.{0,10}(?:用户|个人)?.{0,8}(?:背景|详尽资料)",
        r"(?:无法|难以).{0,12}(?:从中)?(?:提炼|归纳|抽出).{0,10}(?:个性化|针对性)?(?:的)?.{0,6}(?:洞[察见]|洞察)",
        r"(?:无法|未能).{0,12}(?:给出|开展).{0,10}(?:精确|针对性|个性化)?.{0,6}(?:缺口|画像)?分析",
        r"(?i)did\s+not\s+provide.{0,50}(?:background|information|details)",
        r"(?i)has\s+not\s+yet\s+provided.{0,50}(?:background|information|details)?",
        r"(?i)have\s+not\s+provided.{0,40}(?:background|information)",
        r"(?i)not\s+yet\s+provided.{0,30}(?:any\s+)?(?:detailed\s+)?(?:personal\s+)?(?:background|information)",
        r"(?i)lack(?:s|ing).{0,40}(?:specific|detailed|concrete)?.{0,20}user\s+information",
        r"(?i)cannot.{0,30}(?:extract|provide|offer).{0,30}(?:personaliz|individual)",
        r"(?i)due\s+to.{0,20}(?:the\s+)?lack.{0,30}user\s+information",
        r"(?i)without.{0,20}(?:specific|detailed)\s+user",
        r"(?i)general\s+(?:logic|guidance|recommendations?)\s+only",
        r"(?i)unable\s+to.{0,20}(?:extract|provide).{0,30}personal",
    )
    tl = t.lower()
    return any(re.search(p, tl) for p in patterns)


def _survey_field_filled(key: str, answers: dict[str, Any]) -> bool:
    """True when validated survey contributes a substantive value."""
    v = answers.get(key)
    if key == "primary_goals":
        return isinstance(v, list) and len(v) > 0
    return isinstance(v, str) and not _blankish(v)


def _fused_signals(fused_dimensions: dict[str, str], key_memories: list[str]) -> str:
    parts: list[str] = []
    for k in ("life_stage", "family", "finance", "health", "goals", "risk_appetite", "values"):
        parts.append(fused_dimensions.get(k) or "")
    parts.extend(key_memories)
    return "\n".join(parts)


def _follow_up_question_redundant(
    q_raw: str,
    answers: dict[str, Any],
    fused_signals: str,
) -> bool:
    """Drop follow-up bullets that模板式追问已由问卷必填或会话融合画像覆盖的事项。"""
    q = (q_raw or "").strip()
    if not q:
        return True
    ec = str(answers.get("existing_coverage_summary") or "").strip()
    fused = fused_signals.lower()
    qc = q.lower()

    if _survey_field_filled("age_band", answers) and re.search(
        r"(年龄区间|年龄段|年岁|岁数|芳龄)",
        qc,
    ):
        if not re.search(
            r"(受供养|供养|扶养|赡养|家庭成员|同住|抚育|子女|配偶)",
            qc,
        ):
            return True
        if _survey_field_filled("marital_dependents_summary", answers):
            return True
        if re.search(
            r"(单身|已婚|离异|扶养|供养|赡养|子女|配偶|父母|一家)",
            fused,
        ):
            return True

    if (
        _survey_field_filled("income_band", answers)
        and _survey_field_filled("premium_afford_ratio_band", answers)
        and (
            (
                re.search(r"(年收入|月入|可支配收入|月薪|税后|收入水准|收入是否)", qc)
                and re.search(r"(保费|预算|支付|承保|交费|交费比例|可承受)", qc)
            )
            or (
                re.search(r"(一整年|年化|每年).{0,12}(保费|交费)", qc)
                and re.search(r"(区间|预算|上限)", qc)
            )
        )
    ):
        return True

    if not _blankish(ec) and re.search(
        r"(商业保险|其他保险|保单|团体|雇主|公司.*团|团险|团保|vhis)",
        qc,
    ):
        return True
    if (
        _blankish(ec)
        and re.search(r"(是否已有|有没有|是否参加).{0,20}(商业|团体|雇主|公司)", qc)
        and re.search(
            r"(没有|无|未|尚未投保|暂.*无|仅强积金|仅mpf|仅社安|不曾购买|未购买)",
            fused,
        )
    ):
        return True
    if (
        _blankish(ec)
        and re.search(
            r"(商业保险|团体保障|雇员保障|vhis|公司.*(?:医疗|计划))",
            fused,
        )
        and re.search(r"(团体|vhis|商业|雇主|公司)", qc)
    ):
        return True

    hn = str(answers.get("health_notes") or "").strip()
    if hn and len(hn) >= 2:
        if re.search(
            r"(病房级别|私家房|半私家|普通病房|地域覆盖|大中华区|大中华|东亚|跨国|大湾区|北上就医)",
            qc,
        ):
            return True
    return False


def prune_follow_up_questions_after_survey_merge(
    payload: ReportPayload,
    answers: dict[str, Any],
    merged_structured: dict[str, Any] | None,
) -> ReportPayload:
    """Remove template follow-ups already answered by validated survey / fused profile signals."""
    raw = payload.follow_up_questions or []
    if not isinstance(raw, list):
        raw = []

    fused_dims: dict[str, str] = {}
    kms: list[str] = []
    if isinstance(merged_structured, dict):
        dims = merged_structured.get("dimensions")
        if isinstance(dims, dict):
            for k in (
                "finance",
                "family",
                "health",
                "goals",
                "risk_appetite",
                "life_stage",
                "values",
            ):
                fused_dims[k] = str(dims.get(k) or "").strip()
        km = merged_structured.get("key_memories")
        if isinstance(km, list):
            kms = [str(x).strip() for x in km if str(x).strip()]

    signals = _fused_signals(fused_dims, kms)
    kept = [
        x
        for x in raw
        if isinstance(x, str)
        and not _follow_up_question_redundant(x, answers, signals)
    ]
    cleaned = [c.strip() for c in kept if c.strip()]
    return payload.model_copy(update={"follow_up_questions": cleaned[:12]})


def overlay_report_when_model_ignores_survey(
    payload: ReportPayload, answers: dict[str, Any]
) -> ReportPayload:
    """If model still writes 'no user info' boilerplate while survey validated, overwrite prose."""
    bg = payload.user_background or ""
    ins = payload.insights or ""
    need_bg = _text_denies_known_survey_prose(bg) or _boilerplate_conflicts_completed_survey(
        bg, answers
    )
    need_ins = _text_denies_known_survey_prose(ins)
    if not need_bg and not need_ins:
        return payload

    synth_bg = synthesized_user_background_from_survey(answers)
    synth_ins = synthesized_insights_from_survey(answers)
    updates: dict[str, Any] = {}

    if need_bg:
        updates["user_background"] = synth_bg
    if need_ins:
        updates["insights"] = synth_ins

    return payload.model_copy(update=updates)

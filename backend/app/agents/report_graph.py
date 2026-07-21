from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.chart_spec import (
    compute_chart_budget,
    enforce_report_chart_depth,
    sanitize_charts_list,
)
from app.config import get_settings
from app.llm import LLMService, parse_report_json, report_fallback
from app.prompts import REPORT_DEPTH_INSTRUCTIONS, report_json_system
from app.rag.retriever import HybridProductRetriever, retrieval_request_from_profile

logger = logging.getLogger(__name__)


def knowledge_retriever_node(
    state: dict[str, Any], retriever: HybridProductRetriever
) -> dict[str, Any]:
    req = retrieval_request_from_profile(
        state.get("profile_summary") or "",
        state.get("profile_structured"),
        state.get("transcript") or "",
    )
    cands = retriever.retrieve(req)
    return {
        "retrieval_query": req.model_dump(),
        "candidates": [c.model_dump() for c in cands],
        "trace_rationale": "hybrid_keyword_vector_rerank",
    }


def report_architect_node(state: dict[str, Any], llm: LLMService) -> dict[str, Any]:
    from app.locale_support import normalize_locale, output_language_instruction

    cand_dump = json.dumps(state.get("candidates") or [], ensure_ascii=False)
    structured = state.get("profile_structured") if isinstance(state.get("profile_structured"), dict) else {}
    struct_dump = json.dumps(structured, ensure_ascii=False)
    depth = str(state.get("report_depth") or "standard")
    dinstr = REPORT_DEPTH_INSTRUCTIONS.get(
        depth, REPORT_DEPTH_INSTRUCTIONS["standard"]
    )
    loc = normalize_locale(state.get("locale"))
    survey_empty = {
        "en": "(No supplement form excerpt)",
        "zh-TW": "（未提供補充調查表）",
        "zh-CN": "（未提供补充调查表）",
    }[loc]
    survey_txt = (state.get("survey_supplement") or "").strip() or survey_empty
    transcript_full = state.get("transcript") or ""
    transcript_tail = (
        transcript_full[-12000:]
        if isinstance(transcript_full, str) and len(transcript_full) > 12000
        else transcript_full or ""
    )
    fused_empty = {
        "en": "(Empty: rely on structured JSON and survey excerpt only)",
        "zh-TW": "（空：請僅依賴結構化 JSON 與調查表摘錄推導）",
        "zh-CN": "（空：请仅依赖结构化 JSON 与调查表摘录推导）",
    }[loc]
    fused_profile = state.get("profile_summary") or fused_empty
    chart_budget = compute_chart_budget(
        depth,
        optional_filled=int(state.get("survey_optional_filled") or 0),
        structured=structured,
    )
    if loc == "en":
        budget_hint = (
            f"\n[Chart budget] At most **{chart_budget.max_charts}** charts, "
            f"at least **{chart_budget.min_distinct_types}** distinct types; "
            f"aim near **{chart_budget.target_min_count}**. "
            "Titles and data[].name labels must be English.\n"
        )
        prompt = (
            "The fused profile summary already merges chat + supplement form. "
            "Structured JSON is also merged by dimension.\n\n"
            f"[Fused profile summary]\n{fused_profile}\n\n"
            f"[Structured profile JSON]\n{struct_dump}\n\n"
            f"[Supplement form excerpt]\n{survey_txt}\n\n"
            f"[Transcript tail]\n{transcript_tail}\n\n"
            f"{dinstr}\n\n"
            f"[Candidate products JSON — concrete_product_picks may only use these product_id values]\n"
            f"{cand_dump}\n\n"
            "Generate the report JSON. If age/income/family/goals appear in structured JSON or "
            "the survey excerpt, user_background and insights must reflect them — never claim "
            "the user provided no background. limited_data_notice is for product-library limits only."
            + budget_hint
            + "\n"
            + output_language_instruction(loc)
        )
    else:
        budget_hint = (
            f"\n【图表动态预算】根据问卷选填完备度与会话结构化画像信息量，本轮允许 charts 至多 **{chart_budget.max_charts}** 张，"
            f"且在不超过该上限时需要 **不少于 {chart_budget.min_distinct_types} 种**不同的 type（从允许列表择取）；"
            f"条目数可向 **{chart_budget.target_min_count}** 张靠拢。**信息维度越多（财务/家庭/健康/目标/记忆点等），越应拉高图表数量并用多种不同类型表达彼此独立的分析切面**，避免多张图复述同一主轴。\n"
        )
        prompt = (
            "【说明】以下内容中，【融合画像摘要】已由系统在报告前合并「会话对话摘要」"
            "与「补充调查表」两路线索并完成去冗余提示；下面的【结构化画像 JSON】"
            "亦为两路按维度合并后的结果，勿与对话逐字复述混为一谈。\n\n"
            f"【融合画像摘要】\n{fused_profile}\n\n"
            f"【结构化画像 JSON】（会话 + 调查表字段级合并）\n{struct_dump}\n\n"
            f"【补充调查表摘录】（核对细节与原文用词）\n{survey_txt}\n\n"
            f"【对话纪要】（仅尾部节选，供交叉核对；细节以融合摘要与结构化为准）\n{transcript_tail}\n\n"
            f"{dinstr}\n\n"
            f"【候选产品 JSON（concrete_product_picks 只能使用其中 product_id）】\n{cand_dump}\n\n"
            "请生成报告 JSON；charts 须在允许的类型中按结构化画像与深度指令选型；"
            "候选为空时 concrete_product_picks 必须为空数组并强化 limited_data_notice。\n"
            "若「结构化画像 JSON」或「补充调查表摘录」中已有年龄、收入、家庭、目标等信息，"
            "user_background 与 insights 必须据此归纳，不得在正文中笼统声称「用户尚未提供」「缺乏具体背景」；"
            "limited_data_notice 仍可用于说明数据来源与产品检索边界。"
            + budget_hint
        )
    raw = ""
    try:
        settings = get_settings()
        raw = llm.complete_json_text(
            prompt,
            report_json_system(state.get("locale")),
            max_tokens=settings.report_json_max_tokens,
            thinking=True,
        )
        payload = parse_report_json(raw)
    except Exception:
        preview = raw[:4000] if isinstance(raw, str) else ""
        logger.exception(
            "report_architect_failed conversation_id=%s raw_preview_chars=%s",
            state.get("conversation_id"),
            preview,
        )
        payload = report_fallback(state.get("locale"))
    out: dict[str, Any] = {"report_payload_dict": payload.model_dump()}
    if "candidates" in state:
        out["candidates"] = state["candidates"]
    if "retrieval_query" in state:
        out["retrieval_query"] = state["retrieval_query"]
    if "trace_rationale" in state:
        out["trace_rationale"] = state["trace_rationale"]
    return out


def visualizer_agent_node(state: dict[str, Any]) -> dict[str, Any]:
    body = dict(state.get("report_payload_dict") or {})
    depth = str(state.get("report_depth") or "standard")
    structured = state.get("profile_structured") if isinstance(state.get("profile_structured"), dict) else None
    chart_budget = compute_chart_budget(
        depth,
        optional_filled=int(state.get("survey_optional_filled") or 0),
        structured=structured,
    )
    raw_charts = body.get("charts")
    charts = sanitize_charts_list(raw_charts if isinstance(raw_charts, list) else [])
    if isinstance(raw_charts, list) and len(raw_charts) > len(charts):
        logger.warning(
            "report_charts_sanitized conversation_id=%s before=%s after=%s",
            state.get("conversation_id"),
            len(raw_charts),
            len(charts),
        )
    charts = enforce_report_chart_depth(charts, depth, budget=chart_budget)
    if len(charts) < 1:
        fb = report_fallback(state.get("locale"))
        charts = sanitize_charts_list([c.model_dump() for c in fb.charts])
        charts = enforce_report_chart_depth(charts, depth, budget=chart_budget)
    if len(charts) < 1:
        charts = [
            {
                "type": "pie",
                "title": "占位示意",
                "data": [{"name": "示意", "value": 100.0}],
            }
        ]
    body["charts"] = charts[: chart_budget.max_charts]
    return {
        "report_payload_dict": body,
        "candidates": state.get("candidates") or [],
        "retrieval_query": state.get("retrieval_query") or {},
        "trace_rationale": state.get("trace_rationale") or "",
    }


def build_report_graph(llm: LLMService, retriever: HybridProductRetriever):
    g = StateGraph(dict)

    def _kr(s: dict[str, Any]) -> dict[str, Any]:
        return knowledge_retriever_node(s, retriever)

    def _ra(s: dict[str, Any]) -> dict[str, Any]:
        return report_architect_node(s, llm)

    g.add_node("knowledge_retriever", _kr)
    g.add_node("report_architect", _ra)
    g.add_node("visualizer", visualizer_agent_node)
    g.add_edge(START, "knowledge_retriever")
    g.add_edge("knowledge_retriever", "report_architect")
    g.add_edge("report_architect", "visualizer")
    g.add_edge("visualizer", END)
    return g.compile()

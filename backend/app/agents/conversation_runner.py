from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.compliance import (
    assistant_content_for_llm,
    assistant_pipeline_failure_reply,
    chat_reply_has_substantive_body,
    enforce_chat_body_length_range,
    ensure_disclaimer_text,
    normalize_chat_assistant_body,
    second_fallback_for,
    _body_has_substantive_tokens,
    _strip_trailing_disclaimer_blocks,
)
from app.config import Settings, get_settings
from app.llm import LLMService, _strip_think_wrappers
from app.locale_support import normalize_locale
from app.prompts import (
    build_insurance_expert_system,
    profile_structured_json_system,
    rolling_summary_system,
)

logger = logging.getLogger(__name__)

_ANTI_REPEAT_PROSE_BY_LOCALE: dict[str, str] = {
    "zh-CN": "用一段全新的专业中文作答",
    "zh-TW": "用一段全新的專業中文作答",
    "en": "answer in a fresh paragraph of clear professional English",
}


def _raw_has_visible_substance(raw: str | None) -> bool:
    """True if model output has user-visible text before fallback normalization."""
    if raw is None:
        return False
    t = _strip_think_wrappers(str(raw).strip())
    t = _strip_trailing_disclaimer_blocks(t)
    return _body_has_substantive_tokens(t)


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)```$", text)
    if fence:
        text = fence.group(1).strip()
    return text


def format_structured_profile_for_system(blob: Any, max_chars: int) -> str:
    if not isinstance(blob, dict) or not blob:
        return ""
    try:
        raw = json.dumps(blob, ensure_ascii=False)
    except (TypeError, ValueError):
        return ""
    if len(raw) <= max_chars:
        return raw
    logger.warning(
        "structured_profile_truncated chars=%s cap=%s",
        len(raw),
        max_chars,
    )
    slim: dict[str, Any] = {
        "summary_text": blob.get("summary_text"),
        "dimensions": blob.get("dimensions"),
        "key_memories": blob.get("key_memories"),
        "product_focus_categories": blob.get("product_focus_categories"),
        "budget_hint": blob.get("budget_hint"),
    }
    try:
        raw2 = json.dumps(slim, ensure_ascii=False)
    except (TypeError, ValueError):
        return raw[:max_chars] + "\n…(截断)"
    if len(raw2) <= max_chars:
        return raw2
    return raw2[: max_chars - 6] + "\n…(截断)"


def _key_memories_block(kms: Any) -> str:
    if not isinstance(kms, list) or not kms:
        return ""
    rows: list[str] = []
    for x in kms:
        s = str(x).strip()
        if s and s not in rows:
            rows.append(s)
    if not rows:
        return ""
    body = "\n".join(f"- {r}" for r in rows)
    return (
        "【已记住的要点（必须承接；勿重复追问已涵盖的事实；"
        "用户指出重复时先道歉，再换角度推进）】\n" + body
    )


def _build_expert_system(state: dict[str, Any], settings: Settings) -> str:
    system = build_insurance_expert_system(
        settings.chat_body_len_min,
        settings.chat_body_len_max,
        locale=state.get("locale"),
    )
    rs = str(state.get("rolling_summary") or "").strip()
    if rs:
        system = f"{system}\n\n【更早对话摘要】\n{rs}"
    profile_before = state.get("profile_summary") or ""
    if profile_before:
        system = f"{system}\n\n【当前用户画像摘要】{profile_before}"
    struct_block = format_structured_profile_for_system(
        state.get("profile_structured"),
        settings.chat_structured_json_max_chars,
    )
    if struct_block:
        system = f"{system}\n\n【完整结构化画像 JSON】\n{struct_block}"
    km_block = _key_memories_block(state.get("key_memories"))
    if km_block:
        system = f"{system}\n\n{km_block}"
    retrieval_context = str(state.get("retrieval_context") or "").strip()
    if retrieval_context:
        system = f"{system}\n\n【中国人寿海外知识库摘录（可核验）】\n{retrieval_context}"
    return system


def insurance_expert_step(state: dict[str, Any], llm: LLMService) -> dict[str, Any]:
    settings = get_settings()
    loc = normalize_locale(state.get("locale"))
    system = _build_expert_system(state, settings)
    history = state.get("messages_history") or []
    lo, hi = settings.chat_body_len_min, settings.chat_body_len_max
    try:
        reply_raw = llm.chat(history, system, locale=loc)
        if not _raw_has_visible_substance(reply_raw):
            logger.warning(
                "insurance_expert_retry_antirepeat conversation_id=%s user_id=%s",
                state.get("conversation_id"),
                state.get("user_id"),
            )
            prose = _ANTI_REPEAT_PROSE_BY_LOCALE[loc]
            anti_repeat = (
                "\n\n【本轮硬性约束】你必须通读完整对话历史：若用户已说明预算、就医地域/范围、"
                "或已回答你的上一轮追问，**禁止**再用「补充预算/保障缺口」或与上文雷同的套话敷衍，"
                "也不得假装信息仍缺失。你必须在此基础上往前推进一步（例如住院险责任层级、免赔/自付、"
                f"医院网络、或下一步险种取舍），{prose}，不少于 80 字，不得为空。"
            )
            reply_raw = llm.chat(history, system + anti_repeat, locale=loc)
        if not (reply_raw or "").strip():
            logger.error(
                "insurance_expert_empty_llm_reply conversation_id=%s user_id=%s history_msgs=%s",
                state.get("conversation_id"),
                state.get("user_id"),
                len(history),
            )
        body = normalize_chat_assistant_body(reply_raw, locale=loc)
        if not (lo <= len(body) <= hi):
            pre_rewrite = body
            try:
                body = llm.rewrite_chat_body_to_length(body, lo, hi, locale=loc)
                body = _strip_trailing_disclaimer_blocks(body.strip())
                if not chat_reply_has_substantive_body(body):
                    body = enforce_chat_body_length_range(
                        pre_rewrite[:hi], min_len=lo, max_len=hi
                    )
            except Exception:
                logger.exception(
                    "chat_body_rewrite_failed conversation_id=%s user_id=%s",
                    state.get("conversation_id"),
                    state.get("user_id"),
                )
            if not (lo <= len(body) <= hi):
                body = enforce_chat_body_length_range(body, min_len=lo, max_len=hi)
        if not chat_reply_has_substantive_body(body):
            body = enforce_chat_body_length_range(
                second_fallback_for(loc), min_len=lo, max_len=hi
            )
        reply = ensure_disclaimer_text(body, locale=loc)
    except Exception:
        logger.exception(
            "insurance_expert_failed conversation_id=%s user_id=%s",
            state.get("conversation_id"),
            state.get("user_id"),
        )
        reply = assistant_pipeline_failure_reply(loc)
    return {
        "assistant_reply": reply,
        "run_profile_architect": bool(state.get("run_profile_architect")),
    }


def profile_architect_step(state: dict[str, Any], llm: LLMService) -> dict[str, Any]:
    prev_summary = state.get("profile_summary") or ""
    user_msg = state.get("user_message") or ""
    asst = assistant_content_for_llm(str(state.get("assistant_reply") or ""))
    prompt = (
        f"当前摘要：{prev_summary or '尚无'}\n\n"
        f"用户最新输入：{user_msg}\n助手最新回复：{asst}\n\n"
        "请输出结构化画像 JSON。"
    )
    settings = get_settings()
    loc = normalize_locale(state.get("locale"))
    try:
        raw = llm.complete_json_text(
            prompt, profile_structured_json_system(locale=loc)
        )
        text = _strip_json_fence(raw)
        data = json.loads(text)
        summary_new = str(data.get("summary_text", "")).strip()
        kms = data.get("key_memories") or []
        if not isinstance(kms, list):
            kms = []
        kms_clean = [str(x).strip() for x in kms if str(x).strip()][
            : settings.chat_key_memories_inject_max
        ]
        blob = data if isinstance(data, dict) else {}
        return {
            "profile_refresh_done": True,
            "profile_summary_new": summary_new or prev_summary,
            "profile_structured_blob": blob,
            "key_memories_new": kms_clean,
        }
    except Exception:
        logger.exception(
            "profile_architect_failed conversation_id=%s",
            state.get("conversation_id"),
        )
        return {"profile_refresh_done": False}


def merge_rolling_conversation_summary(
    llm: LLMService,
    previous_summary: str,
    older_transcript: str,
    *,
    max_transcript_chars: int = 6000,
    locale: str | None = None,
) -> str:
    """Compress dropped messages into rolling summary (plain text)."""
    chunk = (older_transcript or "").strip()
    if not chunk:
        return (previous_summary or "").strip()
    if len(chunk) > max_transcript_chars:
        chunk = chunk[:max_transcript_chars] + "\n…(片段截断)"
    user_prompt = (
        f"已有更早对话摘要：\n{previous_summary or '（无）'}\n\n"
        f"新增更早对话片段：\n{chunk}"
    )
    loc = normalize_locale(locale)
    try:
        out = llm.chat(
            [{"role": "user", "content": user_prompt}],
            rolling_summary_system(locale=loc),
            locale=loc,
        )
        return (out or "").strip()
    except Exception:
        logger.exception("rolling_summary_merge_failed")
        merged = f"{previous_summary}\n{chunk}".strip()
        return merged[:8000]


def run_conversation_turn(state: dict[str, Any], llm: LLMService) -> dict[str, Any]:
    """Sequential chat: InsuranceExpert then optional ProfileArchitect."""
    out = insurance_expert_step(state, llm)
    if not state.get("run_profile_architect"):
        out["profile_refresh_done"] = False
        return out
    pa = profile_architect_step({**state, **out}, llm)
    out.update(pa)
    return out

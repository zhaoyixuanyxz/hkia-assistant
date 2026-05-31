from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from fastapi import HTTPException, status
from openai import OpenAI

from app.chart_spec import sanitize_charts_list
from app.config import Settings, get_settings
from app.prompts import PROFILE_DUAL_SOURCE_FUSE_MARKER, chat_body_rewrite_system
from app.schemas import ReportPayload

logger = logging.getLogger(__name__)

# Strip inline reasoning blobs some vendors embed in assistant `content` (visible answer may be empty).
_THINK_XML_TAGS: tuple[str, ...] = (
    "think",
    "thinking",
    "thought",
    "reasoning",
    "redacted_reasoning",
    "redacted_thinking",
    "reflection",
)
_THINK_STRIP_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"(?is)<{re.escape(tag)}>[\s\S]*?</{re.escape(tag)}>")
    for tag in _THINK_XML_TAGS
)


def _message_content_to_str(content: Any) -> str:
    """Normalize OpenAI-style message.content (str or list of text parts) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text" and isinstance(part.get("text"), str):
                    chunks.append(part["text"].strip())
            else:
                txt = getattr(part, "text", None)
                if isinstance(txt, str):
                    chunks.append(txt)
        return "".join(chunks).strip()
    return str(content).strip()


def _strip_think_wrappers(text: str) -> str:
    t = text.strip()
    if not t:
        return ""
    for _ in range(4):
        prev = t
        for pat in _THINK_STRIP_PATTERNS:
            t = pat.sub("", t).strip()
        if t == prev:
            break
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _chat_completion_assistant_text(message: Any) -> str:
    """Best-effort assistant text for OpenAI-compatible chat completions.

    DeepSeek reasoner / some gateways put text in ``reasoning_content`` while
    ``content`` is empty; empty ``content`` previously triggered compliance
    fallbacks that look like 'lost memory' repeats.
    """
    primary = _strip_think_wrappers(
        _message_content_to_str(getattr(message, "content", None))
    )
    if primary:
        return primary

    refusal = getattr(message, "refusal", None)
    if isinstance(refusal, str) and refusal.strip():
        return _strip_think_wrappers(refusal.strip())

    for attr in ("reasoning_content", "reasoning", "thinking"):
        chunk = getattr(message, attr, None)
        if isinstance(chunk, str) and chunk.strip():
            logger.warning(
                "chat_completion_using_%s_because_content_empty_chars=%s",
                attr,
                len(chunk),
            )
            return _strip_think_wrappers(chunk.strip())

    extra = getattr(message, "model_extra", None)
    if isinstance(extra, dict):
        for key in ("reasoning_content", "reasoning", "thinking"):
            chunk = extra.get(key)
            if isinstance(chunk, str) and chunk.strip():
                logger.warning(
                    "chat_completion_using_%s_because_content_empty_chars=%s",
                    key,
                    len(chunk),
                )
                return _strip_think_wrappers(chunk.strip())

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        parts: list[str] = []
        for tc in tool_calls:
            func = getattr(tc, "function", None)
            if func is None:
                continue
            args = getattr(func, "arguments", None) or ""
            if isinstance(args, str) and args.strip():
                parts.append(args.strip())
        if parts:
            merged = " ".join(parts)
            logger.warning(
                "chat_completion_using_tool_arguments_because_content_empty chars=%s",
                len(merged),
            )
            return _strip_think_wrappers(merged.strip())

    return ""


class LLMService(ABC):
    @abstractmethod
    def chat(self, messages: list[dict[str, str]], system: str) -> str:
        ...

    @abstractmethod
    def complete_json_text(
        self, user_prompt: str, system: str, *, max_tokens: int | None = None
    ) -> str:
        """Return raw model text expected to be a JSON object."""

    @abstractmethod
    def rewrite_chat_body_to_length(
        self, body: str, min_len: int, max_len: int
    ) -> str:
        """Rewrite advisor-visible body to satisfy min_len <= len(body) <= max_len (no disclaimer)."""


class DeepSeekLLM(LLMService):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: OpenAI | None = None

    def _client_or_raise(self) -> OpenAI:
        if self._client is None:
            key = (self._settings.deepseek_api_key or "").strip()
            if not key:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="DEEPSEEK_API_KEY is not configured",
                )
            self._client = OpenAI(
                api_key=key,
                base_url=self._settings.deepseek_api_base.rstrip("/"),
            )
        return self._client

    def chat(self, messages: list[dict[str, str]], system: str) -> str:
        payload = [{"role": "system", "content": system}]
        payload.extend(messages)
        s = self._settings
        resp = self._client_or_raise().chat.completions.create(
            model=s.deepseek_chat_model,
            messages=payload,
            temperature=s.deepseek_chat_temperature,
            max_tokens=s.deepseek_chat_max_tokens,
        )
        choice = resp.choices[0]
        text = _chat_completion_assistant_text(choice.message)
        if text:
            return text
        logger.warning(
            "deepseek_chat_empty_first_attempt finish_reason=%s",
            getattr(choice, "finish_reason", None),
        )
        retry_system = (
            f"{system}\n\n"
            "【硬性要求·仅本轮】你必须输出一小段中文正文，直接回应用户上一轮内容，"
            "不少于30字且不得为空；不要只输出思考过程或标签。"
        )
        payload_retry = [{"role": "system", "content": retry_system}]
        payload_retry.extend(messages)
        resp2 = self._client_or_raise().chat.completions.create(
            model=s.deepseek_chat_model,
            messages=payload_retry,
            temperature=s.deepseek_chat_retry_temperature,
            max_tokens=s.deepseek_chat_max_tokens,
        )
        text2 = _chat_completion_assistant_text(resp2.choices[0].message)
        if text2:
            return text2
        logger.error(
            "deepseek_chat_empty_after_retry finish_reason=%s refusal=%s tool_calls=%s",
            getattr(resp2.choices[0], "finish_reason", None),
            getattr(resp2.choices[0].message, "refusal", None),
            bool(getattr(resp2.choices[0].message, "tool_calls", None)),
        )
        return ""

    def complete_json_text(
        self, user_prompt: str, system: str, *, max_tokens: int | None = None
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]
        s = self._settings
        cap = max_tokens if max_tokens is not None else min(8192, s.deepseek_chat_max_tokens)
        cap = min(max(cap, 1), 16384)
        resp = self._client_or_raise().chat.completions.create(
            model=self._settings.deepseek_chat_model,
            messages=messages,
            temperature=0.3,
            max_tokens=cap,
        )
        extracted = _chat_completion_assistant_text(resp.choices[0].message)
        if extracted:
            return extracted
        return _message_content_to_str(getattr(resp.choices[0].message, "content", None))

    def rewrite_chat_body_to_length(
        self, body: str, min_len: int, max_len: int
    ) -> str:
        system = chat_body_rewrite_system(min_len, max_len)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": body},
        ]
        resp = self._client_or_raise().chat.completions.create(
            model=self._settings.deepseek_chat_model,
            messages=messages,
            temperature=0.35,
            max_tokens=min(4096, self._settings.deepseek_chat_max_tokens),
        )
        msg = resp.choices[0].message
        text = _chat_completion_assistant_text(msg)
        if text.strip():
            return text.strip()
        logger.warning(
            "rewrite_chat_body_empty finish_reason=%s",
            getattr(resp.choices[0], "finish_reason", None),
        )
        retry_user = (
            f"{body}\n\n（改写助手：上一条未产出正文。请只输出改写后的顾问正文，"
            f"长度须在 {min_len}—{max_len} 字之间，中文，不要思考标签。）"
        )
        messages_retry = [
            {"role": "system", "content": system},
            {"role": "user", "content": retry_user},
        ]
        resp2 = self._client_or_raise().chat.completions.create(
            model=self._settings.deepseek_chat_model,
            messages=messages_retry,
            temperature=0.25,
            max_tokens=min(4096, self._settings.deepseek_chat_max_tokens),
        )
        text2 = _chat_completion_assistant_text(resp2.choices[0].message)
        return (text2 or "").strip()


class MockLLM(LLMService):
    def __init__(
        self,
        chat_reply: str | None = None,
        profile_reply: str | None = None,
        report_json: str | None = None,
    ) -> None:
        self._chat_reply = chat_reply or "先确认：你最担心住院费、重疾还是意外？"
        self._profile_reply = profile_reply or (
            "用户关注家庭保障与储蓄配置，尚在信息收集阶段，风险偏好待确认。"
        )
        self._report_json = report_json
        self._mock_rewrite_template = (
            "收到。我先按你的关注点收敛：在医疗与重疾之间优先厘清住院自付与免赔承受度，"
            "再谈保额与续保稳定性，便于对齐配置与预算。"
            "如需更贴切，请补充一项最关心的保障责任、预算或已有保单线索，便于给出更准确的配置判断。"
        )

    def chat(self, messages: list[dict[str, str]], system: str) -> str:
        if "用户画像摘录" in system or "画像摘录" in system:
            return self._profile_reply
        if "对话摘要助手" in system:
            return (
                "（测试用早期摘要）用户关注家庭医疗保障与支柱人寿；"
                "已提及偏好稳健、希望先厘清预算与自愿医保衔接。"
            )
        return self._chat_reply

    def rewrite_chat_body_to_length(
        self, body: str, min_len: int, max_len: int
    ) -> str:
        s = (body or "").strip()
        if min_len <= len(s) <= max_len:
            return s
        if len(s) > max_len:
            return s[:max_len]
        pad = self._mock_rewrite_template
        while len(s) < min_len and len(s) < max_len:
            s = (s + pad)[:max_len]
        return s

    def complete_json_text(
        self, user_prompt: str, system: str, *, max_tokens: int | None = None
    ) -> str:
        if PROFILE_DUAL_SOURCE_FUSE_MARKER in system:
            return json.dumps(
                {
                    "integrated_summary": (
                        "（测试双线融合）会话画像侧重家庭医疗与预算衔接；"
                        "补充调查表勾选住院/医疗费用保障，年龄区间 25–34，常住香港，"
                        "可动用收入与保费承受能力已在表中披露，两路合并后作为检索与报告依据。"
                    ),
                },
                ensure_ascii=False,
            )
        if self._report_json:
            return self._report_json
        if "结构化画像JSON助手" in system:
            return json.dumps(
                {
                    "summary_text": self._profile_reply,
                    "dimensions": {
                        "finance": "",
                        "family": "二孩家庭（示意），信息尚在收集",
                        "health": "",
                        "goals": "完善医疗保障与支柱寿险",
                        "risk_appetite": "稳健偏保守（示意）",
                        "life_stage": "中青年家庭（示意）",
                        "values": "稳健优先（示意）",
                    },
                    "key_memories": ["关注家庭保障", "偏好稳健思路（示意）"],
                    "product_focus_categories": ["医疗", "人寿"],
                    "budget_hint": "",
                },
                ensure_ascii=False,
            )
        payload = ReportPayload(
            title="示例配置说明（测试）",
            user_background="根据对话整理的背景摘要。",
            insights="家庭保障与长期储蓄需平衡流动性与跨境安排。",
            allocation_direction="优先完善医疗保障与家庭支柱人寿保障，再考虑储蓄型产品框架。",
            product_category_suggestions="医疗保险、定期人寿、储蓄分红（示例类别，非具体产品推荐）。",
            risk_notes="汇率、流动性及理赔定义差异需单独评估。",
            follow_up_questions=["可接受的保费预算？", "有无自願醫保或公司团险？"],
            charts=[
                {
                    "type": "radar",
                    "title": "保障维度示意",
                    "data": [
                        {"name": "医疗", "value": 65},
                        {"name": "人寿", "value": 55},
                        {"name": "重疾", "value": 45},
                    ],
                },
                {
                    "type": "pie",
                    "title": "配置比例示意（示例）",
                    "data": [
                        {"name": "保障", "value": 55},
                        {"name": "储蓄", "value": 30},
                        {"name": "现金储备", "value": 15},
                    ],
                },
            ],
            concrete_product_picks=[],
            disclaimer="",
        )
        return payload.model_dump_json()


_default_llm: LLMService | None = None


def get_llm_service() -> LLMService:
    global _default_llm
    s = get_settings()
    if s.use_mock_llm:
        return MockLLM()
    if _default_llm is None:
        _default_llm = DeepSeekLLM(s)
    return _default_llm


def reset_llm_singleton() -> None:
    global _default_llm
    _default_llm = None


def _decode_report_json_object(text: str) -> dict[str, Any] | None:
    """Recover a single JSON object from model output (preamble, fences, or extra text)."""
    t = _strip_think_wrappers(text.strip())
    if not t:
        return None

    def _try_loads(chunk: str) -> dict[str, Any] | None:
        chunk = chunk.strip()
        if not chunk:
            return None
        try:
            data = json.loads(chunk)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
        decoder = json.JSONDecoder()
        i = 0
        while True:
            j = chunk.find("{", i)
            if j < 0:
                return None
            try:
                obj, end = decoder.raw_decode(chunk, j)
                if isinstance(obj, dict):
                    return obj
                i = end
            except json.JSONDecodeError:
                i = j + 1

    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)```$", t)
    if fence:
        got = _try_loads(fence.group(1))
        if got is not None:
            return got

    got = _try_loads(t)
    if got is not None:
        return got
    return None


_STR_KEYS_REPORT = frozenset(
    {
        "title",
        "user_background",
        "insights",
        "allocation_direction",
        "product_category_suggestions",
        "risk_notes",
        "limited_data_notice",
        "disclaimer",
    },
)


def _coerce_report_dict(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    for k in _STR_KEYS_REPORT:
        if k not in out:
            continue
        v = out[k]
        if v is not None and not isinstance(v, str):
            out[k] = str(v)
    fu = out.get("follow_up_questions")
    if fu is None:
        out["follow_up_questions"] = []
    elif isinstance(fu, str):
        s = fu.strip()
        out["follow_up_questions"] = [s] if s else []
    elif isinstance(fu, list):
        out["follow_up_questions"] = [
            str(x).strip() for x in fu if isinstance(x, (str, int, float)) and str(x).strip()
        ]
    else:
        out["follow_up_questions"] = []
    cpp = out.get("concrete_product_picks")
    if cpp is None or not isinstance(cpp, list):
        out["concrete_product_picks"] = []
    else:
        norm: list[dict[str, Any]] = []
        for item in cpp:
            if isinstance(item, dict):
                norm.append(item)
        out["concrete_product_picks"] = norm
    ch = out.get("charts")
    if isinstance(ch, dict):
        out["charts"] = [ch]
    elif not isinstance(ch, list):
        out["charts"] = []
    return out


def parse_report_json(raw: str) -> ReportPayload:
    data = _decode_report_json_object(raw)
    if data is None:
        raise ValueError("parse_report_json: could not decode a JSON object from model output")
    coerced = _coerce_report_dict(data)
    if isinstance(coerced.get("charts"), list):
        coerced["charts"] = sanitize_charts_list(coerced["charts"])
    return ReportPayload.model_validate(coerced)


def report_fallback() -> ReportPayload:
    from app.compliance import STANDARD_DISCLAIMER

    return ReportPayload(
        title="配置说明（系统兜底）",
        user_background="由于模型输出解析失败，以下为框架性占位说明；请重新生成或联系支持。",
        insights="信息不足，无法在自动化流程中得出可靠洞察。",
        allocation_direction="建议先澄清预算、家庭结构与已有保障。",
        product_category_suggestions="请在持牌顾问协助下选择具体产品类别。",
        risk_notes="勿依赖本占位文本做购买决策。",
        follow_up_questions=["请补充年龄、职业、家庭负担与币种偏好。"],
        charts=[
            {
                "type": "line",
                "title": "时间线占位（示例）",
                "data": [
                    {"name": "T0", "value": 1},
                    {"name": "T1", "value": 2},
                    {"name": "T2", "value": 3},
                ],
            },
        ],
        limited_data_notice="当前内容非模型有效输出，仅为系统兜底；数据来源有限。",
        disclaimer=STANDARD_DISCLAIMER,
        concrete_product_picks=[],
    )

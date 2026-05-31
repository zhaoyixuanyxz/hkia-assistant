from __future__ import annotations

import logging
import unicodedata

from app.config import get_settings

logger = logging.getLogger(__name__)

STANDARD_DISCLAIMER = (
    "本内容由 AI 根据用户提供的信息和公开资料生成，仅供一般信息参考，不构成持牌财务、保险、税务、法律或投资建议。"
    "保险产品条款、费用、收益、保障范围和适用性应以保险公司正式文件及持牌专业人士意见为准。"
    "请在作出任何购买或配置决定前，咨询合资格专业顾问。"
)

SHORT_DISCLAIMER = (
    "以上内容仅供参考，不构成持牌建议。正式条款及适合性请以保险公司文件与合资格顾问意见为准。"
)

# 模型偶发只输出空串或纯标点时，避免出现「仅免责声明、无正文」；须落在 CHAT_BODY_LEN_* 区间内
CHAT_ASSISTANT_EMPTY_BODY_FALLBACK = (
    "收到。刚才未拿到可用的模型正文，我会继续沿用你已在对话里说过的事实与偏好，不让你重复陈述。"
    "为继续细化配置，请你用一句话点出下一步最关心的是「住院保障范围」「免赔与自付」还是「重疾给付形态」之一；"
    "若暂不确定，可直接回复「按你的建议往下推」。"
)

CHAT_ASSISTANT_SECOND_FALLBACK = (
    "收到。我会继续基于上下文给出判断。"
    "请先说明你此刻在「住院/重疾保障责任」「产品类别取舍」或「核保与健康告知疑虑」中，最想先厘清的一项具体点（已说过的预算与地域不必重复）。"
)

# 用于将过短正文专业地补长到区间内（从长到短尝试，优先一次即落入 [min,max]）
_LENGTH_PAD_SUFFIXES: tuple[str, ...] = (
    "如需更贴切，请补充一项最关心的保障责任、预算或已有保单线索，便于给出更准确的配置判断。",
    "请补充最关心的保障或预算一项关键信息，以便更准确。",
    "请补充一项关键信息以便更准确。",
    "请先说明一项预算或保障关注，便于对齐。",
    "以便继续细化。",
)

# Longest first: strip trailing footers to detect empty substantive body
_DISCLAIMER_SUFFIXES_STRIP: tuple[str, ...] = (
    STANDARD_DISCLAIMER,
    "「以上内容仅供一般信息参考，不构成持牌财务、保险、税务或法律建议；具体条款以保险公司正式文件及合资格专业人士意见为准。」",
    "以上内容仅供一般信息参考，不构成持牌财务、保险、税务或法律建议；具体条款以保险公司正式文件及合资格专业人士意见为准。",
    SHORT_DISCLAIMER,
)


def _strip_trailing_disclaimer_blocks(text: str) -> str:
    t = text.strip()
    changed = True
    while changed and t:
        changed = False
        for suffix in _DISCLAIMER_SUFFIXES_STRIP:
            if t.endswith(suffix):
                t = t[: -len(suffix)].rstrip()
                if t.endswith("\n\n"):
                    t = t[:-2].rstrip()
                changed = True
                break
    return t.strip()


def _body_has_substantive_tokens(body: str) -> bool:
    """True if visible text has at least one Unicode letter or number.

    The old ASCII+CJK-BMP-only regex misclassified rare ideographs, fullwidth
    digits-only snippets, and some scripts as 'empty', triggering the canned
    fallback that looks like forgotten context.
    """
    s = body.strip()
    if not s:
        return False
    for ch in s:
        if ch.isspace():
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("L") or cat.startswith("N"):
            return True
    return False


def _join_body_and_suffix(body: str, suffix: str) -> str:
    b = body.rstrip()
    su = (suffix or "").strip()
    if not b:
        return su
    if not su:
        return b
    if b[-1] in "。！？…」』":
        return f"{b}{su}"
    return f"{b}。{su}"


def _body_len_bounds(
    min_len: int | None,
    max_len: int | None,
) -> tuple[int, int]:
    if min_len is not None and max_len is not None:
        return min_len, max_len
    s = get_settings()
    return s.chat_body_len_min, s.chat_body_len_max


def enforce_chat_body_length_range(
    body: str,
    min_len: int | None = None,
    max_len: int | None = None,
) -> str:
    """Clamp assistant-visible body to [min_len, max_len] characters (Python len)."""
    lo, hi = _body_len_bounds(min_len, max_len)
    s = (body or "").strip()
    if len(s) > hi:
        s = s[:hi]
    if lo <= len(s) <= hi:
        return s
    for suf in _LENGTH_PAD_SUFFIXES:
        cand = _join_body_and_suffix(s, suf)
        if lo <= len(cand) <= hi:
            return cand
    best = ""
    for suf in _LENGTH_PAD_SUFFIXES:
        cand = _join_body_and_suffix(s, suf)
        if len(cand) > hi:
            continue
        if len(cand) >= lo:
            return cand
        if len(cand) > len(best):
            best = cand
    frag = (
        "为更准确匹配你的情况，也请补充一项最关心的保障缺口或预算区间；"
        "若已有自愿医保或公司团险也可一并说明。"
    )
    while len(s) < lo:
        cand = _join_body_and_suffix(s, frag)
        if len(cand) <= hi:
            s = cand
        else:
            if len(s) < hi:
                s = (s + frag)[:hi]
            break
    if len(s) >= lo:
        return s
    if len(best) >= lo:
        return best
    return enforce_chat_body_length_range(
        CHAT_ASSISTANT_EMPTY_BODY_FALLBACK.strip(), min_len=lo, max_len=hi
    )


def assistant_content_for_llm(stored_assistant_message: str) -> str:
    """Strip persisted compliance footers so the model sees only the user-facing reply body."""
    stripped = _strip_trailing_disclaimer_blocks(stored_assistant_message or "")
    if stripped:
        return stripped
    s = (stored_assistant_message or "").strip()
    return s if s else "(上一轮助手正文缺失)"


def chat_reply_has_substantive_body(text: str | None) -> bool:
    """True if message has visible content beyond known compliance footers."""
    return _body_has_substantive_tokens(_strip_trailing_disclaimer_blocks(text or ""))


def normalize_chat_assistant_body(raw: str | None) -> str:
    """Strip trailing disclaimer blocks; apply empty-body fallbacks. Does not enforce length."""
    body = _strip_trailing_disclaimer_blocks((raw or "").strip())
    if not _body_has_substantive_tokens(body):
        logger.warning("chat_assistant_empty_body_fallback applied")
        body = CHAT_ASSISTANT_EMPTY_BODY_FALLBACK
    if not _body_has_substantive_tokens(body):
        logger.error("chat_assistant_empty_body_fallback_invalid")
        body = CHAT_ASSISTANT_SECOND_FALLBACK
    return body.strip()


def finalize_chat_assistant_text(raw: str | None) -> str:
    """Router / persistence guard: ensure disclaimer and length in case graph skipped steps."""
    lo, hi = _body_len_bounds(None, None)
    body = normalize_chat_assistant_body(raw)
    if not (lo <= len(body) <= hi):
        body = enforce_chat_body_length_range(body, min_len=lo, max_len=hi)
    return ensure_disclaimer_text(body)


def ensure_disclaimer_text(text: str | None) -> str:
    """Ensure the standard footer appears exactly once (suffix match)."""
    base = (text or "").strip()
    if not base:
        return STANDARD_DISCLAIMER
    if base.endswith(STANDARD_DISCLAIMER):
        return base
    return f"{base}\n\n{STANDARD_DISCLAIMER}"


def merge_report_disclaimer(body_disclaimer: str | None) -> str:
    return ensure_disclaimer_text(body_disclaimer or STANDARD_DISCLAIMER)


def assistant_pipeline_failure_reply() -> str:
    base = "抱歉，顾问助手暂时不可用，您的这条消息已保存，请稍后重试。"
    return ensure_disclaimer_text(base)

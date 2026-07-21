from __future__ import annotations

SUPPORTED_LOCALES: frozenset[str] = frozenset({"zh-CN", "en", "zh-TW"})
DEFAULT_LOCALE = "zh-CN"

_OUTPUT_LANGUAGE: dict[str, str] = {
    "zh-CN": (
        "【输出语言】本轮所有面向用户的正文、追问、摘要字段值必须使用**简体中文**。"
        "JSON 键名保持英文；产品正式名称/计划代码保持知识库原文。"
    ),
    "zh-TW": (
        "【输出语言】本輪所有面向用戶的正文、追問、摘要字段值必須使用**繁體中文**。"
        "JSON 鍵名保持英文；產品正式名稱/計劃代碼保持知識庫原文。"
    ),
    "en": (
        "【Output language】All user-facing prose, follow-up questions, and string field values "
        "in this turn MUST be written in professional, prudent **English**. "
        "Keep JSON keys in English. Keep official product/plan names and codes as in the knowledge "
        "base (add a short English gloss in parentheses only if helpful). "
        "Do not invent translated formal policy titles."
    ),
}


def normalize_locale(value: str | None) -> str:
    if value is None:
        return DEFAULT_LOCALE
    s = str(value).strip()
    if s in SUPPORTED_LOCALES:
        return s
    return DEFAULT_LOCALE


def output_language_instruction(locale: str | None) -> str:
    loc = normalize_locale(locale)
    return _OUTPUT_LANGUAGE[loc]

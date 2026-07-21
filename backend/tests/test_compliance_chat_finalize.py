from __future__ import annotations

from app.compliance import (
    STANDARD_DISCLAIMER,
    assistant_content_for_llm,
    disclaimer_for,
    finalize_chat_assistant_text,
)
from app.config import get_settings


def _bounds() -> tuple[int, int]:
    lo, hi = get_settings().chat_body_len_min, get_settings().chat_body_len_max
    return lo, hi


def test_finalize_chat_empty_raw_gets_fallback_body() -> None:
    lo, hi = _bounds()
    out = finalize_chat_assistant_text("")
    assert STANDARD_DISCLAIMER in out
    body = assistant_content_for_llm(out)
    assert lo <= len(body) <= hi
    assert "收到" in body


def test_finalize_chat_preserves_model_short_reply() -> None:
    lo, hi = _bounds()
    out = finalize_chat_assistant_text("先看重疾方向")
    body = assistant_content_for_llm(out)
    assert lo <= len(body) <= hi
    assert "先看重疾方向" in body
    assert STANDARD_DISCLAIMER in out


def test_finalize_truncates_long_reply() -> None:
    lo, hi = _bounds()
    raw = "诊" * (hi + 50)
    out = finalize_chat_assistant_text(raw)
    body = assistant_content_for_llm(out)
    assert len(body) == hi
    assert STANDARD_DISCLAIMER in out


def test_finalize_chat_disclaimer_only_string_gets_fallback() -> None:
    lo, hi = _bounds()
    out = finalize_chat_assistant_text(STANDARD_DISCLAIMER)
    body = assistant_content_for_llm(out)
    assert lo <= len(body) <= hi
    assert "收到" in body
    assert STANDARD_DISCLAIMER in out


def test_finalize_chat_punctuation_only_gets_fallback() -> None:
    lo, hi = _bounds()
    out = finalize_chat_assistant_text("…")
    body = assistant_content_for_llm(out)
    assert lo <= len(body) <= hi
    assert STANDARD_DISCLAIMER in out


def test_assistant_content_for_llm_strips_standard_footer() -> None:
    body = "已了解，您关注医疗保障。"
    stored = f"{body}\n\n{STANDARD_DISCLAIMER}"
    assert assistant_content_for_llm(stored) == body


def test_finalize_leading_whitespace_then_only_standard_disclaimer_gets_fallback() -> None:
    lo, hi = _bounds()
    out = finalize_chat_assistant_text(f"\n\n{STANDARD_DISCLAIMER}")
    body = assistant_content_for_llm(out)
    assert lo <= len(body) <= hi
    assert "收到" in body
    assert STANDARD_DISCLAIMER in out


def test_assistant_content_for_llm_strips_english_footer() -> None:
    en = disclaimer_for("en")
    body = "Hospital cover first."
    stored = f"{body}\n\n{en}"
    assert assistant_content_for_llm(stored) == body

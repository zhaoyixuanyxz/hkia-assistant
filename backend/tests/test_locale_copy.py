from app.compliance import (
    disclaimer_for,
    short_disclaimer_for,
    empty_body_fallback_for,
    failure_reply_for,
    ensure_disclaimer_text,
    _strip_trailing_disclaimer_blocks,
)
from app.llm import report_fallback


def test_disclaimer_three_locales_distinct() -> None:
    zh = disclaimer_for("zh-CN")
    en = disclaimer_for("en")
    tw = disclaimer_for("zh-TW")
    assert zh and en and tw
    assert len({zh, en, tw}) == 3
    assert "AI" in en or "artificial" in en.lower() or "reference" in en.lower()
    assert "持牌" in zh


def test_ensure_disclaimer_uses_locale_footer() -> None:
    body = "Here is advice about hospital cover."
    out = ensure_disclaimer_text(body, locale="en")
    assert out.endswith(disclaimer_for("en"))
    assert disclaimer_for("zh-CN") not in out


def test_strip_english_disclaimer_suffix() -> None:
    en = disclaimer_for("en")
    body = "Hospital cover first."
    stored = f"{body}\n\n{en}"
    assert _strip_trailing_disclaimer_blocks(stored) == body


def test_failure_reply_english() -> None:
    text = failure_reply_for("en")
    assert "temporarily unavailable" in text.lower() or "try again" in text.lower()
    assert disclaimer_for("en") in text


def test_report_fallback_en_title() -> None:
    fb = report_fallback("en")
    assert (
        "fallback" in fb.title.lower()
        or "system" in fb.title.lower()
        or "placeholder" in fb.title.lower()
    )
    assert fb.disclaimer == disclaimer_for("en")


def test_conversation_runner_passes_locale_en() -> None:
    from unittest.mock import MagicMock

    from app.agents.conversation_runner import run_conversation_turn
    from app.llm import LLMService

    llm = MagicMock(spec=LLMService)
    body = (
        "Got it. Let's focus on hospital cover first: deductible, co-pay, and network. "
        "Share your budget band or existing VHIS if any, and I will narrow next steps "
        "without repeating questions you already answered about your family priorities."
    )
    llm.chat.return_value = body

    def _rewrite(text: str, min_len: int, max_len: int, *, locale: str | None = None) -> str:
        s = text.strip()
        if min_len <= len(s) <= max_len:
            return s
        if len(s) > max_len:
            return s[:max_len]
        pad = (
            " I will keep refining hospital coverage, deductible tolerance, and critical-illness "
            "design in clear professional English until the reply meets the length band."
        )
        while len(s) < min_len and len(s) < max_len:
            s = (s + pad)[:max_len]
        return s

    llm.rewrite_chat_body_to_length.side_effect = _rewrite
    out = run_conversation_turn(
        {
            "conversation_id": 1,
            "user_id": 1,
            "user_message": "hello",
            "messages_history": [{"role": "user", "content": "hello"}],
            "profile_summary": "",
            "profile_structured": None,
            "key_memories": [],
            "retrieval_context": "",
            "run_profile_architect": False,
            "rolling_summary": "",
            "locale": "en",
        },
        llm,
    )
    assert out.get("assistant_reply", "").endswith(disclaimer_for("en"))
    assert disclaimer_for("zh-CN") not in out.get("assistant_reply", "")
    assert llm.chat.call_args.kwargs.get("locale") == "en"
    if llm.rewrite_chat_body_to_length.called:
        assert llm.rewrite_chat_body_to_length.call_args.kwargs.get("locale") == "en"

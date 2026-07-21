from app.compliance import (
    disclaimer_for,
    short_disclaimer_for,
    empty_body_fallback_for,
    failure_reply_for,
    ensure_disclaimer_text,
    _strip_trailing_disclaimer_blocks,
)


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

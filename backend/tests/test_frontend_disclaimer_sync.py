"""Frontend chat-disclaimer.ts must mirror compliance.py disclaimer strings."""

from pathlib import Path

from app.compliance import SHORT_DISCLAIMERS, STANDARD_DISCLAIMERS

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DISCLAIMER = REPO_ROOT / "frontend" / "lib" / "chat-disclaimer.ts"


def test_frontend_disclaimer_contains_all_locale_strings() -> None:
    text = FRONTEND_DISCLAIMER.read_text(encoding="utf-8")

    assert STANDARD_DISCLAIMERS["zh-CN"] in text
    assert STANDARD_DISCLAIMERS["en"] in text
    assert STANDARD_DISCLAIMERS["zh-TW"] in text
    assert SHORT_DISCLAIMERS["en"] in text
    assert SHORT_DISCLAIMERS["zh-TW"] in text

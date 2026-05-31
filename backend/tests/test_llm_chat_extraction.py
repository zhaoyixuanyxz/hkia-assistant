from __future__ import annotations

from types import SimpleNamespace

from app.llm import _chat_completion_assistant_text


def test_extract_prefers_nonempty_content() -> None:
    msg = SimpleNamespace(content="  hello  ", refusal=None, model_extra=None)
    assert _chat_completion_assistant_text(msg) == "hello"


def test_extract_reasoning_when_content_empty() -> None:
    msg = SimpleNamespace(
        content="",
        refusal=None,
        reasoning_content="  需要先确认预算  ",
        model_extra=None,
    )
    assert _chat_completion_assistant_text(msg) == "需要先确认预算"


def test_extract_list_text_parts() -> None:
    msg = SimpleNamespace(
        content=[{"type": "text", "text": "  第一部  "}, {"type": "text", "text": "第二部"}],
        refusal=None,
        model_extra=None,
    )
    assert _chat_completion_assistant_text(msg) == "第一部第二部"


def test_extract_strips_xml_thinking_wrappers() -> None:
    raw = "<think>忽略</think>已了解，按无团险先配实报实销思路推进。"
    msg = SimpleNamespace(content=raw, refusal=None, model_extra=None)
    out = _chat_completion_assistant_text(msg)
    assert "已了解" in out
    assert "redacted_thinking" not in out

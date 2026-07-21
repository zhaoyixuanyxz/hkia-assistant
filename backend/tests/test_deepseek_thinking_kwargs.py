from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.config import Settings
from app.llm import DeepSeekLLM


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        msg = SimpleNamespace(
            content='{"ok":true}',
            refusal=None,
            model_extra=None,
            reasoning_content=None,
            tool_calls=None,
        )
        choice = SimpleNamespace(message=msg, finish_reason="stop")
        return SimpleNamespace(choices=[choice])


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = _FakeChat(completions)


def _settings(**overrides: Any) -> Settings:
    """Build Settings without relying on field names (validation_alias only)."""
    env = {
        "DEEPSEEK_API_KEY": "test-key",
        "DEEPSEEK_API_BASE": "https://api.deepseek.com/v1",
        "DEEPSEEK_CHAT_MODEL": "deepseek-v4-pro",
        "DEEPSEEK_REPORT_THINKING": "true",
        "DEEPSEEK_REPORT_REASONING_EFFORT": "high",
    }
    # Map pythonic override keys to env aliases used by Settings.
    key_map = {
        "deepseek_api_key": "DEEPSEEK_API_KEY",
        "deepseek_api_base": "DEEPSEEK_API_BASE",
        "deepseek_chat_model": "DEEPSEEK_CHAT_MODEL",
        "deepseek_report_thinking": "DEEPSEEK_REPORT_THINKING",
        "deepseek_report_reasoning_effort": "DEEPSEEK_REPORT_REASONING_EFFORT",
    }
    for k, v in overrides.items():
        env_key = key_map.get(k, k)
        if isinstance(v, bool):
            env[env_key] = "true" if v else "false"
        else:
            env[env_key] = str(v)
    return Settings(_env_file=None, **env)


def test_chat_disables_thinking() -> None:
    fake = _FakeCompletions()
    llm = DeepSeekLLM(_settings())
    llm._client = _FakeClient(fake)  # type: ignore[assignment]

    out = llm.chat([{"role": "user", "content": "你好"}], "sys")
    assert out
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["model"] == "deepseek-v4-pro"
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "temperature" in call
    assert "reasoning_effort" not in call


def test_complete_json_default_disables_thinking() -> None:
    fake = _FakeCompletions()
    llm = DeepSeekLLM(_settings())
    llm._client = _FakeClient(fake)  # type: ignore[assignment]

    llm.complete_json_text("{}", "profile system")
    call = fake.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert call.get("temperature") == 0.3
    assert "reasoning_effort" not in call


def test_complete_json_thinking_true_enables_report_thinking() -> None:
    fake = _FakeCompletions()
    llm = DeepSeekLLM(_settings())
    llm._client = _FakeClient(fake)  # type: ignore[assignment]

    llm.complete_json_text("{}", "report system", thinking=True, max_tokens=2048)
    call = fake.calls[0]
    assert call["model"] == "deepseek-v4-pro"
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}
    assert call["reasoning_effort"] == "high"
    assert "temperature" not in call


def test_complete_json_thinking_true_respects_config_off() -> None:
    fake = _FakeCompletions()
    llm = DeepSeekLLM(_settings(deepseek_report_thinking=False))
    llm._client = _FakeClient(fake)  # type: ignore[assignment]

    llm.complete_json_text("{}", "report system", thinking=True)
    call = fake.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in call


def test_rewrite_disables_thinking() -> None:
    fake = _FakeCompletions()
    llm = DeepSeekLLM(_settings())
    llm._client = _FakeClient(fake)  # type: ignore[assignment]

    llm.rewrite_chat_body_to_length("短", 200, 1200)
    call = fake.calls[0]
    assert call["extra_body"] == {"thinking": {"type": "disabled"}}

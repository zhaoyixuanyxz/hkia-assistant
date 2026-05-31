from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.prompts import INSURANCE_EXPERT_SYSTEM


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compose_backend_uses_live_llm_by_default() -> None:
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'USE_MOCK_LLM: "true"' not in compose_text
    assert 'USE_MOCK_LLM: "${USE_MOCK_LLM:-false}"' in compose_text
    assert "DEEPSEEK_API_KEY:" in compose_text
    assert "EMBEDDING_API_KEY:" in compose_text


def test_settings_accept_legacy_deepseek_env_names(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "example-chat")

    settings = Settings(_env_file=None)

    assert settings.deepseek_api_base == "https://api.example.test"
    assert settings.deepseek_chat_model == "example-chat"


def test_settings_report_follow_up_defaults_to_empty_no_followup_list() -> None:
    settings = Settings(_env_file=None)
    assert settings.report_follow_up_mode == "empty"


def test_insurance_expert_prompt_requires_consultative_dialogue() -> None:
    assert "中国人寿人寿保险（海外）股份有限公司" in INSURANCE_EXPERT_SYSTEM
    assert "禁止越界推荐" in INSURANCE_EXPERT_SYSTEM
    assert "家庭顾问" in INSURANCE_EXPERT_SYSTEM
    assert "一至两个本公司方向性结论" in INSURANCE_EXPERT_SYSTEM
    assert "禁止不当优越与笼统比较用词" in INSURANCE_EXPERT_SYSTEM
    assert "完全抛弃固定问答流程" in INSURANCE_EXPERT_SYSTEM
    assert "不要重复上一轮已经问过的问题" in INSURANCE_EXPERT_SYSTEM
    assert "200—1200 个字符" in INSURANCE_EXPERT_SYSTEM
    assert "额外调用一次模型" in INSURANCE_EXPERT_SYSTEM
    assert "不要在正文中写出任何免责声明" in INSURANCE_EXPERT_SYSTEM
    assert "优先控制在**一个**最关键" in INSURANCE_EXPERT_SYSTEM

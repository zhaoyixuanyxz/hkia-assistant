from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_base: str = Field(
        default="https://api.deepseek.com/v1",
        validation_alias=AliasChoices("DEEPSEEK_API_BASE", "DEEPSEEK_BASE_URL"),
    )
    deepseek_api_key: str = ""
    deepseek_chat_model: str = Field(
        default="deepseek-v4-pro",
        validation_alias=AliasChoices("DEEPSEEK_CHAT_MODEL", "DEEPSEEK_MODEL"),
    )
    #: Report-path JSON calls (dual-source fuse + report architect): enable DeepSeek thinking.
    deepseek_report_thinking: bool = Field(
        default=True,
        validation_alias=AliasChoices("DEEPSEEK_REPORT_THINKING"),
    )
    #: DeepSeek reasoning_effort when report thinking is on (`high` or `max`).
    deepseek_report_reasoning_effort: str = Field(
        default="high",
        validation_alias=AliasChoices("DEEPSEEK_REPORT_REASONING_EFFORT"),
    )

    use_mock_llm: bool = False

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # SQLite default for quick dev/tests; phase 2 production uses PostgreSQL + Alembic
    database_url: str = "sqlite:///./hkia.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_products: str = "knowledge_products"
    qdrant_collection_memory: str = "user_long_term_memory"

    embedding_api_base: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"

    profile_refresh_every_n_user_turns: int = 2

    # Injected into chat LLM system context (deduped merge of snapshot + Qdrant)
    chat_key_memories_inject_max: int = 28
    chat_key_memories_merge_cap: int = 40
    chat_qdrant_memory_search_limit: int = 24

    # Advisor reply body length (before auto-appended STANDARD_DISCLAIMER)
    chat_body_len_min: int = 200
    chat_body_len_max: int = 1200

    # Sliding window of user+assistant messages passed to chat completion
    chat_history_max_messages: int = 100

    # Cap for serialized structured_json block in system prompt (chars)
    chat_structured_json_max_chars: int = 12000

    deepseek_chat_temperature: float = 0.78
    deepseek_chat_retry_temperature: float = 0.45
    deepseek_chat_max_tokens: int = 4096
    report_json_max_tokens: int = Field(
        default=16384,
        description="报告 JSON 单次补全上限；多图（至多 20 张）时需更大上下文，过小易截断 JSON 触发兜底",
    )
    #: 生成报告时已通过问卷必填校验：`empty`=不展示「后续澄清」列表（硬性）；`pruned`=仅用规则裁剪模型给出的追问
    report_follow_up_mode: Literal["empty", "prune"] = Field(
        default="empty",
        validation_alias=AliasChoices("REPORT_FOLLOW_UP_MODE"),
    )

    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "hkia"

    force_memory_checkpointer: bool = False
    admin_api_key: str = ""
    admin_bootstrap_emails: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

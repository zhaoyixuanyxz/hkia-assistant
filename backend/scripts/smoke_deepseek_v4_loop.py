"""Live smoke: DeepSeek V4 Pro chat (no thinking) + report JSON (thinking).

Run from backend/:
  .venv\\Scripts\\python.exe scripts/smoke_deepseek_v4_loop.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings, get_settings
from app.llm import DeepSeekLLM, parse_report_json
from app.prompts import (
    INSURANCE_EXPERT_SYSTEM,
    PROFILE_DUAL_SOURCE_FUSE_SYSTEM,
    REPORT_JSON_SYSTEM,
)


def main() -> int:
    get_settings.cache_clear()
    s = Settings()  # loads repo .env
    if not (s.deepseek_api_key or "").strip():
        print("FAIL: DEEPSEEK_API_KEY missing")
        return 2
    print("model=", s.deepseek_chat_model)
    print("report_thinking=", s.deepseek_report_thinking, s.deepseek_report_reasoning_effort)

    llm = DeepSeekLLM(s)

    # 1) Chat path — thinking disabled
    t0 = time.perf_counter()
    chat = llm.chat(
        [{"role": "user", "content": "我在香港工作，想先了解住院医疗保障，预算大概每月几千港币。"}],
        INSURANCE_EXPERT_SYSTEM[:1200] + "\n（冒烟测试：请用中文简短回复，约80–150字。）",
    )
    dt_chat = time.perf_counter() - t0
    print(f"CHAT ok chars={len(chat)} seconds={dt_chat:.1f}")
    print("CHAT preview:", (chat or "")[:180].replace("\n", " "))
    if len((chat or "").strip()) < 20:
        print("FAIL: chat reply too short")
        return 1

    # 2) Dual-source fuse — thinking enabled
    t1 = time.perf_counter()
    fuse_raw = llm.complete_json_text(
        (
            "【对话画像摘要】关注住院医疗，香港雇员，预算每月几千港币。\n\n"
            '【会话结构化 JSON】{"dimensions":{"goals":"医疗住院","life_stage":"25-34"}}\n\n'
            "【补充调查表摘录】年龄25-34，常住香港，目标 medical_hospital。\n\n"
            '只输出 JSON：{"integrated_summary":"..."}'
        ),
        PROFILE_DUAL_SOURCE_FUSE_SYSTEM,
        thinking=True,
        max_tokens=2048,
    )
    dt_fuse = time.perf_counter() - t1
    fuse_obj = json.loads(fuse_raw[fuse_raw.find("{") : fuse_raw.rfind("}") + 1])
    summ = fuse_obj.get("integrated_summary") or ""
    print(f"FUSE ok chars={len(summ)} seconds={dt_fuse:.1f}")
    if len(summ) < 40:
        print("FAIL: fuse summary too short", fuse_raw[:300])
        return 1

    # 3) Report architect — thinking enabled
    t2 = time.perf_counter()
    report_raw = llm.complete_json_text(
        (
            f"【融合画像摘要】\n{summ}\n\n"
            '【结构化画像 JSON】{"dimensions":{"goals":"医疗住院","life_stage":"25-34","finance":"预算每月几千港币"}}\n\n'
            "【补充调查表摘录】年龄25-34，香港，目标住院医疗。\n\n"
            "【对话纪要】用户想了解住院医疗保障。\n\n"
            "【候选产品 JSON】[]\n\n"
            "请生成报告 JSON；concrete_product_picks 为空数组。"
        ),
        REPORT_JSON_SYSTEM,
        thinking=True,
        max_tokens=min(8192, s.report_json_max_tokens),
    )
    dt_rep = time.perf_counter() - t2
    payload = parse_report_json(report_raw)
    print(
        f"REPORT ok title={payload.title!r} insights_chars={len(payload.insights or '')} "
        f"seconds={dt_rep:.1f}"
    )
    if not (payload.title and payload.insights and payload.allocation_direction):
        print("FAIL: report missing core fields")
        return 1

    print("PASS live closed-loop (chat + fuse + report) on", s.deepseek_chat_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

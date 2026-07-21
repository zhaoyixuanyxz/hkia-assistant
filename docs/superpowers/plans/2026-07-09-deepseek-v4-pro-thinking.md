# DeepSeek V4 Pro Thinking Split Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Switch all generative LLM calls to `deepseek-v4-pro`; disable thinking on chat path; enable thinking on report fuse + report architect.

**Architecture:** Single model name via existing settings; `DeepSeekLLM` centralizes OpenAI-compatible `thinking` / `reasoning_effort` kwargs; report call sites pass `thinking=True`.

**Tech Stack:** FastAPI, OpenAI Python SDK, pytest, DeepSeek OpenAI-compatible API

---

### Task 1: Config defaults + env docs

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `backend/tests/test_agent_runtime_config.py`

- [x] Default model `deepseek-v4-pro`; add report thinking settings
- [x] Update compose default model + pass-through env
- [x] Assert defaults in tests

### Task 2: LLM layer thinking switch

**Files:**
- Modify: `backend/app/llm.py`
- Create: `backend/tests/test_deepseek_thinking_kwargs.py`

- [x] Add `_create_completion` with thinking on/off
- [x] Wire `chat` / rewrite / `complete_json_text(thinking=...)`
- [x] Unit tests with mocked OpenAI client capturing kwargs

### Task 3: Report call sites

**Files:**
- Modify: `backend/app/report_integrated_profile.py`
- Modify: `backend/app/agents/report_graph.py`
- Modify: `backend/tests/test_report_integrated_profile.py` (if signature assertions needed)

- [x] Pass `thinking=True` on fuse + report architect

### Task 4: Verify

- [x] `pytest` backend suite (76 passed, 1 skipped)
- [x] Live closed-loop smoke (`backend/scripts/smoke_deepseek_v4_loop.py`)

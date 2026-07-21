# Locale-Aware Chat & Report Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chat replies, profile/report LLM text, disclaimers, and fallbacks follow the current UI locale (`zh-CN` | `en` | `zh-TW`) via request body `locale`, without rewriting history or persisting locale on conversations.

**Architecture:** Request-scoped `locale` on message send/edit and report generate. Backend `normalize_locale()` feeds prompt output-language blocks plus multilingual copy tables in `compliance`. Frontend passes `useLocale()` in JSON bodies; `chat-disclaimer.ts` strips all three disclaimer footers.

**Tech Stack:** FastAPI, Pydantic, LangGraph runners, next-intl, pytest, Vitest/Jest if present (else manual + backend tests for disclaimer sync).

**Spec:** `docs/superpowers/specs/2026-07-21-locale-aware-generation-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Create `backend/app/locale_support.py` | `SUPPORTED_LOCALES`, `normalize_locale`, `output_language_instruction` |
| Modify `backend/app/compliance.py` | Locale-keyed disclaimer/fallback copy; locale params on finalize helpers |
| Modify `backend/app/prompts.py` | Locale-aware system builders / report & profile systems |
| Modify `backend/app/llm.py` | Pass locale into rewrite + empty-retry strings; `report_fallback(locale)` |
| Modify `backend/app/agents/conversation_runner.py` | Read `state["locale"]`; wire locale through expert/profile/rolling |
| Modify `backend/app/agents/report_graph.py` | `report_json_system(locale)`; `report_fallback(locale)` |
| Modify `backend/app/report_integrated_profile.py` | Fuse system + call with locale |
| Modify `backend/app/schemas.py` | `MessageCreate.locale`; `ReportGenerateBody` |
| Modify `backend/app/routers/conversations.py` | Pass locale into chat turn + report generate |
| Modify `frontend/lib/chat-disclaimer.ts` | EN + zh-TW disclaimer suffixes |
| Modify `frontend/app/[locale]/(app)/conversations/[id]/chat/page.tsx` | Send/edit with locale |
| Modify `frontend/app/[locale]/(app)/conversations/[id]/report/page.tsx` | Generate with locale |
| Create `backend/tests/test_locale_support.py` | normalize + language block |
| Create/extend `backend/tests/test_locale_copy.py` | disclaimer/fallback/report_fallback per locale |
| Extend `backend/tests/test_compliance_chat_finalize.py` | locale-aware finalize + strip EN footer |
| Create `backend/tests/test_locale_prompts.py` | prompt builders contain language instructions |
| Extend API tests as needed for optional `locale` body |

---

### Task 1: `normalize_locale` + output language instruction

**Files:**
- Create: `backend/app/locale_support.py`
- Create: `backend/tests/test_locale_support.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_locale_support.py
from app.locale_support import normalize_locale, output_language_instruction


def test_normalize_locale_accepts_supported() -> None:
    assert normalize_locale("zh-CN") == "zh-CN"
    assert normalize_locale("en") == "en"
    assert normalize_locale("zh-TW") == "zh-TW"


def test_normalize_locale_defaults() -> None:
    assert normalize_locale(None) == "zh-CN"
    assert normalize_locale("") == "zh-CN"
    assert normalize_locale("fr") == "zh-CN"
    assert normalize_locale("EN") == "zh-CN"  # exact match only; no case fold


def test_output_language_instruction_en_mentions_english() -> None:
    text = output_language_instruction("en")
    assert "English" in text
    assert "简体中文" not in text


def test_output_language_instruction_zh_tw() -> None:
    text = output_language_instruction("zh-TW")
    assert "繁體中文" in text
```

- [ ] **Step 2: Run tests — expect fail (module missing)**

Run: `cd backend && python -m pytest tests/test_locale_support.py -v`  
Expected: `ModuleNotFoundError` or import error for `app.locale_support`

- [ ] **Step 3: Implement `locale_support.py`**

```python
# backend/app/locale_support.py
from __future__ import annotations

SUPPORTED_LOCALES: frozenset[str] = frozenset({"zh-CN", "en", "zh-TW"})
DEFAULT_LOCALE = "zh-CN"

_OUTPUT_LANGUAGE: dict[str, str] = {
    "zh-CN": (
        "【输出语言】本轮所有面向用户的正文、追问、摘要字段值必须使用**简体中文**。"
        "JSON 键名保持英文；产品正式名称/计划代码保持知识库原文。"
    ),
    "zh-TW": (
        "【输出语言】本輪所有面向用戶的正文、追問、摘要字段值必須使用**繁體中文**。"
        "JSON 鍵名保持英文；產品正式名稱/計劃代碼保持知識庫原文。"
    ),
    "en": (
        "【Output language】All user-facing prose, follow-up questions, and string field values "
        "in this turn MUST be written in professional, prudent **English**. "
        "Keep JSON keys in English. Keep official product/plan names and codes as in the knowledge "
        "base (add a short English gloss in parentheses only if helpful). "
        "Do not invent translated formal policy titles."
    ),
}


def normalize_locale(value: str | None) -> str:
    if value is None:
        return DEFAULT_LOCALE
    s = str(value).strip()
    if s in SUPPORTED_LOCALES:
        return s
    return DEFAULT_LOCALE


def output_language_instruction(locale: str | None) -> str:
    loc = normalize_locale(locale)
    return _OUTPUT_LANGUAGE[loc]
```

- [ ] **Step 4: Run tests — expect pass**

Run: `cd backend && python -m pytest tests/test_locale_support.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/locale_support.py backend/tests/test_locale_support.py
git commit -m "feat: add locale normalize and output-language instructions"
```

---

### Task 2: Multilingual compliance copy

**Files:**
- Modify: `backend/app/compliance.py`
- Create: `backend/tests/test_locale_copy.py`
- Modify: `backend/tests/test_compliance_chat_finalize.py` (keep zh-CN defaults green; add EN strip test)

- [ ] **Step 1: Write failing tests for copy helpers**

```python
# backend/tests/test_locale_copy.py
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
```

- [ ] **Step 2: Run — expect fail**

Run: `cd backend && python -m pytest tests/test_locale_copy.py -v`  
Expected: FAIL (missing functions)

- [ ] **Step 3: Implement copy tables + locale-aware helpers in `compliance.py`**

Keep module-level aliases for backward compatibility:

```python
# Conceptual shape — implement fully in file:

STANDARD_DISCLAIMERS: dict[str, str] = {
    "zh-CN": "本内容由 AI …咨询合资格专业顾问。",  # existing text
    "zh-TW": "本內容由 AI …諮詢合資格專業顧問。",  # Traditional of same meaning
    "en": (
        "This content is generated by AI from information you provided and publicly available "
        "materials. It is for general information only and does not constitute licensed financial, "
        "insurance, tax, legal, or investment advice. Product terms, fees, benefits, coverage, and "
        "suitability are subject to the insurer's official documents and advice from licensed "
        "professionals. Please consult a qualified adviser before any purchase or configuration decision."
    ),
}

# Same pattern for SHORT_DISCLAIMERS, EMPTY_BODY_FALLBACKS, SECOND_FALLBACKS,
# FAILURE_BASES, optional LENGTH_PAD_SUFFIXES_BY_LOCALE

def disclaimer_for(locale: str | None) -> str: ...
def short_disclaimer_for(locale: str | None) -> str: ...
def empty_body_fallback_for(locale: str | None) -> str: ...
def second_fallback_for(locale: str | None) -> str: ...
def failure_reply_for(locale: str | None) -> str:
    # ensure_disclaimer_text(base, locale=locale)

STANDARD_DISCLAIMER = STANDARD_DISCLAIMERS["zh-CN"]  # keep existing import sites working
SHORT_DISCLAIMER = SHORT_DISCLAIMERS["zh-CN"]
CHAT_ASSISTANT_EMPTY_BODY_FALLBACK = EMPTY_BODY_FALLBACKS["zh-CN"]
CHAT_ASSISTANT_SECOND_FALLBACK = SECOND_FALLBACKS["zh-CN"]

# _DISCLAIMER_SUFFIXES_STRIP must include ALL locale standard + short strings (longest first)

def ensure_disclaimer_text(text: str | None, *, locale: str | None = None) -> str:
    disc = disclaimer_for(locale)
    ...

def normalize_chat_assistant_body(raw: str | None, *, locale: str | None = None) -> str:
    # use empty_body_fallback_for(locale) / second_fallback_for(locale)

def finalize_chat_assistant_text(raw: str | None, *, locale: str | None = None) -> str:
    ...

def merge_report_disclaimer(body_disclaimer: str | None, *, locale: str | None = None) -> str:
    ...

def assistant_pipeline_failure_reply(locale: str | None = None) -> str:
    return failure_reply_for(locale)

# enforce_chat_body_length_range: when padding, prefer locale pad suffixes if provided;
# default zh-CN pads to keep existing tests stable when locale omitted
```

English empty-body fallback (must be long enough for `chat_body_len_min` after length enforce — mirror Chinese substance):

```text
Got it. I did not receive a usable model reply just now; I will keep using the facts and preferences
you already shared and will not ask you to repeat them. To refine the plan, reply in one sentence
with whether you care most about hospital coverage scope, deductible/co-pay, or critical-illness
benefit design; if unsure, reply "please proceed with your recommendation."
```

- [ ] **Step 4: Update `test_compliance_chat_finalize.py` if signatures changed** — calls without locale must still pass (default `zh-CN`).

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_locale_copy.py tests/test_compliance_chat_finalize.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/compliance.py backend/tests/test_locale_copy.py backend/tests/test_compliance_chat_finalize.py
git commit -m "feat: multilingual disclaimers and chat fallbacks by locale"
```

---

### Task 3: Locale-aware prompts

**Files:**
- Modify: `backend/app/prompts.py`
- Create: `backend/tests/test_locale_prompts.py`

- [ ] **Step 1: Write failing prompt tests**

```python
# backend/tests/test_locale_prompts.py
from app.prompts import (
    build_insurance_expert_system,
    chat_body_rewrite_system,
    profile_structured_json_system,
    rolling_summary_system,
    profile_dual_source_fuse_system,
    report_json_system,
)


def test_expert_system_en_has_output_language_not_forced_zh() -> None:
    s = build_insurance_expert_system(200, 1200, locale="en")
    assert "English" in s or "Output language" in s
    assert "必须使用**简体中文**" not in s
    # must not contain the old hard-coded rewrite-only phrase as the sole language rule
    assert "改写成一段专业、审慎的中文" not in s


def test_rewrite_system_follows_locale() -> None:
    zh = chat_body_rewrite_system(200, 1200, locale="zh-CN")
    en = chat_body_rewrite_system(200, 1200, locale="en")
    assert "简体" in zh or "中文" in zh
    assert "English" in en or "英文" in en


def test_report_json_system_en() -> None:
    s = report_json_system(locale="en")
    assert "English" in s or "Output language" in s
    assert "均为中文内容字符串" not in s
```

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Refactor `prompts.py`**

1. `build_insurance_expert_system(min_len, max_len, locale: str | None = None)` — append `output_language_instruction(locale)` at end; remove any implication that body must be Chinese-only if present.
2. `chat_body_rewrite_system(min_len, max_len, locale: str | None = None)` — replace「改写成一段专业、审慎的中文」with locale-aware wording + append language instruction.
3. Replace module constants that hard-code 中文 with functions:
   - `profile_structured_json_system(locale=None)`
   - `rolling_summary_system(locale=None)`
   - `profile_dual_source_fuse_system(locale=None)` (keep exporting `PROFILE_DUAL_SOURCE_FUSE_MARKER`)
   - `report_json_system(locale=None)` — replace「JSON 字段（均为中文内容字符串…）」with「string values in the output language for locale …」
4. Keep thin aliases if tests import old names:

```python
INSURANCE_EXPERT_SYSTEM = build_insurance_expert_system(200, 1200)
PROFILE_STRUCTURED_JSON_SYSTEM = profile_structured_json_system()
ROLLING_SUMMARY_SYSTEM = rolling_summary_system()
PROFILE_DUAL_SOURCE_FUSE_SYSTEM = profile_dual_source_fuse_system()
REPORT_JSON_SYSTEM = report_json_system()
```

- [ ] **Step 4: Fix any import breakages** from renamed symbols (grep `PROFILE_STRUCTURED_JSON_SYSTEM`, `REPORT_JSON_SYSTEM`, etc.) — aliases above should keep most green.

- [ ] **Step 5: Run**

Run: `cd backend && python -m pytest tests/test_locale_prompts.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/prompts.py backend/tests/test_locale_prompts.py
git commit -m "feat: inject output-language constraints into agent prompts"
```

---

### Task 4: Wire locale through runners, LLM rewrite, report fuse/fallback

**Files:**
- Modify: `backend/app/llm.py` (`rewrite_chat_body_to_length(..., locale=None)`, empty-retry strings, `report_fallback(locale=None)`)
- Modify: `backend/app/agents/conversation_runner.py`
- Modify: `backend/app/agents/report_graph.py`
- Modify: `backend/app/report_integrated_profile.py`
- Modify: `backend/tests/test_phase4_charts.py` / `test_report_integrated_profile.py` if signatures need defaults

- [ ] **Step 1: Update `report_fallback`**

```python
def report_fallback(locale: str | None = None) -> ReportPayload:
    from app.compliance import disclaimer_for
    from app.locale_support import normalize_locale
    loc = normalize_locale(locale)
    # dict of per-locale field strings; zh-CN = existing Chinese placeholder text
    ...
    return ReportPayload(..., disclaimer=disclaimer_for(loc), ...)
```

Add test in `test_locale_copy.py`:

```python
from app.llm import report_fallback

def test_report_fallback_en_title() -> None:
    fb = report_fallback("en")
    assert "fallback" in fb.title.lower() or "system" in fb.title.lower() or "placeholder" in fb.title.lower()
    assert fb.disclaimer == disclaimer_for("en")
```

- [ ] **Step 2: `DeepSeekLLM.rewrite_chat_body_to_length(self, body, min_len, max_len, *, locale=None)`** — pass locale into `chat_body_rewrite_system`; change retry user string from「中文」to locale instruction snippet.

- [ ] **Step 3: `DeepSeekLLM.chat` empty retry** — replace hard-coded「一小段中文正文」with text derived from `output_language_instruction` **only if** we can pass locale into `chat`. Prefer: add optional `locale: str | None = None` to `chat()` and use it in retry_system; default `zh-CN` preserves behavior. Call sites in `conversation_runner` pass `state` locale.

- [ ] **Step 4: `conversation_runner.py`**

- `_build_expert_system(state, settings)` → `build_insurance_expert_system(..., locale=state.get("locale"))`
- Anti-repeat block: replace「专业中文」with locale-aware phrase (e.g. EN: "in clear professional English")
- `normalize_chat_assistant_body` / `ensure_disclaimer_text` / `assistant_pipeline_failure_reply` / second fallback → pass `locale=state.get("locale")`
- `rewrite_chat_body_to_length(..., locale=...)`
- `profile_architect_step`: `profile_structured_json_system(locale=...)`
- `merge_rolling_conversation_summary(..., locale=None)`: use `rolling_summary_system(locale)`

- [ ] **Step 5: `report_integrated_profile.py`**

```python
def fuse_profile_summary_dual_source(..., locale: str | None = None):
    ...
    raw = llm.complete_json_text(
        user, profile_dual_source_fuse_system(locale), thinking=True
    )

def build_integrated_profile_for_report(..., locale: str | None = None):
    ...
    summary, fuse_mode = fuse_profile_summary_dual_source(..., locale=locale)
```

- [ ] **Step 6: `report_graph.py`**

- `report_architect_node`: `system = report_json_system(state.get("locale"))`; on failure `report_fallback(state.get("locale"))`
- `visualizer_agent_node`: `report_fallback(state.get("locale"))` when charts empty

- [ ] **Step 7: Run focused tests**

Run: `cd backend && python -m pytest tests/test_locale_copy.py tests/test_report_integrated_profile.py tests/test_phase4_charts.py tests/test_phase2_graph.py -v`  
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/llm.py backend/app/agents/conversation_runner.py backend/app/agents/report_graph.py backend/app/report_integrated_profile.py backend/tests/test_locale_copy.py
git commit -m "feat: pass locale through chat runner, rewrite, and report graph"
```

---

### Task 5: API schemas + router wiring

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/conversations.py`
- Modify or create: `backend/tests/test_locale_api.py` (mock LLM via existing app fixtures)

- [ ] **Step 1: Schema changes**

```python
# schemas.py
class MessageCreate(BaseModel):
    content: str
    locale: str | None = None


class ReportGenerateBody(BaseModel):
    locale: str | None = None
```

- [ ] **Step 2: Wire `_complete_chat_turn(..., locale: str | None = None)`**

```python
from app.locale_support import normalize_locale

def _complete_chat_turn(..., locale: str | None = None) -> list[MessageOut]:
    loc = normalize_locale(locale)
    ...
    out = run_conversation_turn({..., "locale": loc}, llm)
    # on outer except: assistant_pipeline_failure_reply(loc)
    # wherever finalize_chat_assistant_text / ensure_disclaimer used: locale=loc
```

`post_message` / `patch_user_message`:

```python
return _complete_chat_turn(db, conv, user, llm, user_msg, locale=body.locale)
```

- [ ] **Step 3: `generate_report`**

```python
@router.post("/{conversation_id}/reports/generate", response_model=ReportOut)
def generate_report(
    conversation_id: int,
    body: ReportGenerateBody | None = None,
    ...
):
    loc = normalize_locale(body.locale if body else None)
    ...
    profile, structured, fuse_mode = build_integrated_profile_for_report(
        ..., locale=loc
    )
    ...
    rout = rg.invoke({..., "locale": loc})
    ...
    disc = merge_report_disclaimer(payload.disclaimer, locale=loc)
```

If FastAPI rejects optional body on POST with no content-type, prefer:

```python
body: ReportGenerateBody = Body(default_factory=ReportGenerateBody),
```

so `{}` / empty still works for old clients.

- [ ] **Step 4: API test (reuse TestClient + MockLLM pattern from `test_mvp_flow.py`)**

```python
def test_post_message_accepts_locale_en(client, ...):
    # create conv, POST {"content": "Hello", "locale": "en"}
    # assert 200; with MockLLM, reply may still be Chinese mock text —
    # assert request path does not 422; optionally assert disclaimer_for("en") in assistant message
```

For MockLLM: either extend mock to append `disclaimer_for(locale)` via runner (already does `ensure_disclaimer_text`), so assistant content should end with English disclaimer when locale=en.

- [ ] **Step 5: Run**

Run: `cd backend && python -m pytest tests/test_locale_api.py tests/test_mvp_flow.py tests/test_edit_user_message.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/conversations.py backend/tests/test_locale_api.py
git commit -m "feat: accept locale on message and report generate APIs"
```

---

### Task 6: Frontend pass locale + disclaimer strip sync

**Files:**
- Modify: `frontend/lib/chat-disclaimer.ts`
- Modify: `frontend/app/[locale]/(app)/conversations/[id]/chat/page.tsx`
- Modify: `frontend/app/[locale]/(app)/conversations/[id]/report/page.tsx`
- Optional: add a tiny unit test if the frontend already has a test runner for `lib/`; otherwise verify strip logic manually / with a small node assert script.

- [ ] **Step 1: Sync disclaimer suffixes**

Export constants matching backend `disclaimer_for` / `short_disclaimer_for` for `en` and `zh-TW` (copy exact strings from `compliance.py`). Add to `DISCLAIMER_SUFFIXES` array (longest first). Keep Chinese entries.

- [ ] **Step 2: Chat page**

```tsx
import { useLocale } from "next-intl";
// inside component:
const locale = useLocale();

// send:
body: JSON.stringify({ content: text, locale }),

// saveEdit:
body: JSON.stringify({ content: text, locale }),
```

- [ ] **Step 3: Report page**

```tsx
const locale = useLocale();
const rep = await apiFetchWithTimeout<ReportResponse>(
  `/conversations/${id}/reports/generate`,
  { method: "POST", body: JSON.stringify({ locale }) },
  120_000
);
```

- [ ] **Step 4: Quick strip check**

In a REPL or one-off test: `splitAssistantMessage(body + "\\n\\n" + EN_DISCLAIMER)` returns `{ body, disclaimer: EN_DISCLAIMER }`.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/chat-disclaimer.ts frontend/app/[locale]/(app)/conversations/[id]/chat/page.tsx frontend/app/[locale]/(app)/conversations/[id]/report/page.tsx
git commit -m "feat: send UI locale on chat/report requests; strip EN/TW disclaimers"
```

---

### Task 7: Regression sweep + manual checklist

**Files:** none new (verification only)

- [ ] **Step 1: Full backend pytest**

Run: `cd backend && python -m pytest -q`  
Expected: all green (fix any locale-default breakage from signature changes)

- [ ] **Step 2: Manual checklist (from spec)**

1. UI → English → new chat reply + footer English; old Chinese bubbles unchanged  
2. Switch back to zh-CN → new reply Simplified  
3. English → generate report → narrative English; product official names may stay original  
4. zh-TW UI smoke one turn  
5. Force pipeline failure / empty body → fallback language matches UI  

- [ ] **Step 3: Final commit only if leftover fixes** (message: `fix: locale-aware generation edge cases`)

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Request-scoped locale, no DB column | 5 |
| MessageCreate + report generate body | 5 |
| Default zh-CN / normalize | 1, 5 |
| Prompt output-language block; no hard-coded 中文-only | 3, 4 |
| Disclaimer / empty / failure / report_fallback tables | 2, 4 |
| Strip suffixes sync FE+BE | 2, 6 |
| Frontend useLocale in bodies | 6 |
| History unchanged on switch | (behavior; no rewrite code) |
| Product names not inventively translated | 1 language block text |
| Tests listed in spec | 1–5, 7 |

## Out of scope (do not implement)

- Auto language detection from user text  
- Translating history  
- `conversation.locale` column  
- Full triple translation of master system prompts  
- Localizing all HTTP validation `detail` strings

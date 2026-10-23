# US-3 Excerpt-Month Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop report picks whose `excerpt_date` month is earlier than the Hong Kong calendar month of report generation, or cannot be parsed to a month.

**Architecture:** Add `filter_picks_current_excerpt_month` in `report_products.py`; call it immediately after each `filter_picks_requiring_three_fields` on the report generate path. Parse only `YYYY-MM-DD` / `YYYY-MM`. Inject `now` for tests. No narrative scrub.

**Tech Stack:** FastAPI, Pydantic, pytest, `zoneinfo.ZoneInfo("Asia/Hong_Kong")`.

**Spec:** `docs/superpowers/specs/2026-10-23-us3-excerpt-month-gate-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Modify `backend/app/report_products.py` | Month parse + filter helper |
| Modify `backend/app/routers/conversations.py` | Call after each three-field filter |
| Modify `backend/tests/test_report_products.py` | AC-1–4 unit tests |

---

### Task 1: Month filter helper + unit tests

**Files:**
- Modify: `backend/app/report_products.py`
- Test: `backend/tests/test_report_products.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_report_products.py` (reuse `_pick` from US-2 if present; otherwise define it):

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.report_products import filter_picks_current_excerpt_month

HK = ZoneInfo("Asia/Hong_Kong")


def test_month_filter_drops_earlier_month() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-09-30")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert out.concrete_product_picks == []


def test_month_filter_keeps_same_month() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-10-01")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert len(out.concrete_product_picks) == 1


def test_month_filter_keeps_yyyy_mm() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-10")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert len(out.concrete_product_picks) == 1


def test_month_filter_drops_unparseable() -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="not-a-month")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert out.concrete_product_picks == []


def test_month_filter_uses_hk_boundary_now() -> None:
    # Just into October HK; September excerpt must drop.
    now = datetime(2026, 10, 1, 0, 5, tzinfo=HK)
    payload = ReportPayload(
        concrete_product_picks=[_pick(excerpt_date="2026-09-30")]
    )
    out = filter_picks_current_excerpt_month(payload, now=now)
    assert out.concrete_product_picks == []
```

- [ ] **Step 2: Run — expect fail**

```
cd backend
uv run python -m pytest tests/test_report_products.py -k month_filter -v --basetemp=.pytest_basetemp
```

Expected: FAIL (function missing)

- [ ] **Step 3: Implement filter**

```python
# In backend/app/report_products.py
from datetime import datetime
from zoneinfo import ZoneInfo

_HK = ZoneInfo("Asia/Hong_Kong")


def _excerpt_year_month(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 7 and text[4] == "-":
        # YYYY-MM or YYYY-MM-DD
        try:
            year = int(text[0:4])
            month = int(text[5:7])
        except ValueError:
            return None
        if month < 1 or month > 12:
            return None
        if len(text) == 7:
            return year, month
        if len(text) >= 10 and text[7] == "-":
            try:
                day = int(text[8:10])
            except ValueError:
                return None
            if day < 1 or day > 31:
                return None
            return year, month
    return None


def filter_picks_current_excerpt_month(
    payload: ReportPayload,
    *,
    now: datetime | None = None,
) -> ReportPayload:
    clock = now if now is not None else datetime.now(_HK)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=_HK)
    else:
        clock = clock.astimezone(_HK)
    report_ym = (clock.year, clock.month)
    kept = [
        p
        for p in payload.concrete_product_picks
        if _excerpt_year_month(p.excerpt_date) == report_ym
    ]
    return payload.model_copy(update={"concrete_product_picks": kept})
```

- [ ] **Step 4: Run — expect pass**

```
cd backend
uv run python -m pytest tests/test_report_products.py -v --basetemp=.pytest_basetemp
```

Expected: all PASS

- [ ] **Step 5: Commit** (only if operator asked)

```bash
git add backend/app/report_products.py backend/tests/test_report_products.py
git commit -m "feat(report): drop picks whose excerpt month is not current HK month"
```

---

### Task 2: Wire month filter on report generate path

**Files:**
- Modify: `backend/app/routers/conversations.py` (~888–893)

- [ ] **Step 1: Import and call after each three-field filter**

Update import:

```python
from app.report_products import (
    enrich_product_picks_with_sources,
    filter_picks_current_excerpt_month,
    filter_picks_requiring_three_fields,
    hydrate_concrete_picks_from_candidates,
    sanitize_concrete_product_picks,
)
```

Replace the two gate sites with:

```python
payload = filter_picks_requiring_three_fields(payload)
payload = filter_picks_current_excerpt_month(payload)
payload = enforce_report_output_locale(
    payload, survey_answers, locale=loc, llm=llm
)
# EN locale rewrite may strip sum_assured/premium/excerpt_date from model JSON.
payload = filter_picks_requiring_three_fields(payload)
payload = filter_picks_current_excerpt_month(payload)
```

- [ ] **Step 2: Run tests**

```
cd backend
uv run python -m pytest tests/test_report_products.py -v --basetemp=.pytest_basetemp
```

Expected: PASS

- [ ] **Step 3: Commit** (only if operator asked)

```bash
git add backend/app/routers/conversations.py docs/superpowers/specs/2026-10-23-us3-excerpt-month-gate-design.md docs/superpowers/plans/2026-10-23-us3-excerpt-month-gate.md
git commit -m "feat(report): apply excerpt-month gate after three-field filter"
```

---

## Spec coverage self-check

| Spec | Task |
|------|------|
| Month helper + HK now | Task 1 |
| YYYY-MM-DD / YYYY-MM parse; else drop | Task 1 |
| After each three-field filter | Task 2 |
| AC-1–4 unit tests | Task 1 |
| No narrative scrub | Out of scope |

## Placeholder / consistency self-check

- Field name `excerpt_date` matches US-1/2/5
- No TBD

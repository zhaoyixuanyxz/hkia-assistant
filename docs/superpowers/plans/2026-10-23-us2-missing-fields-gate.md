# US-2 Missing-Fields Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop report picks missing `sum_assured`, `premium`, or `excerpt_date` so they never appear in the customer comparison list (structured refs only).

**Architecture:** Add `filter_picks_requiring_three_fields` in `report_products.py`; call it once after sanitize → enrich → hydrate on the report generate path. Blank/whitespace counts as missing. No narrative scrub. No month-expiry (US-3).

**Tech Stack:** FastAPI, Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-us2-missing-fields-gate-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Modify `backend/app/report_products.py` | Filter helper |
| Modify `backend/app/routers/conversations.py` | Call filter after hydrate |
| Modify `backend/tests/test_report_products.py` | AC-1–4 structured tests |

---

### Task 1: Filter helper + unit tests

**Files:**
- Modify: `backend/app/report_products.py`
- Test: `backend/tests/test_report_products.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to backend/tests/test_report_products.py
from app.report_products import filter_picks_requiring_three_fields
from app.schemas import ReportPayload, ReportProductPick


def _pick(**kwargs) -> ReportProductPick:
    base = dict(
        product_id="p1",
        name="n",
        rationale="r",
        sum_assured="HKD 1",
        premium="HKD 2",
        excerpt_date="2026-10-01",
    )
    base.update(kwargs)
    return ReportProductPick(**base)


def test_filter_drops_missing_sum_assured() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick(sum_assured=None)])
    out = filter_picks_requiring_three_fields(payload)
    assert out.concrete_product_picks == []


def test_filter_drops_missing_premium() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick(premium="  ")])
    out = filter_picks_requiring_three_fields(payload)
    assert out.concrete_product_picks == []


def test_filter_drops_missing_excerpt_date() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick(excerpt_date=None)])
    out = filter_picks_requiring_three_fields(payload)
    assert out.concrete_product_picks == []


def test_filter_keeps_complete_pick() -> None:
    payload = ReportPayload(concrete_product_picks=[_pick()])
    out = filter_picks_requiring_three_fields(payload)
    assert len(out.concrete_product_picks) == 1
    assert out.concrete_product_picks[0].product_id == "p1"


def test_filter_after_hydrate_drops_incomplete_candidate() -> None:
    from app.report_products import hydrate_concrete_picks_from_candidates

    payload = ReportPayload(concrete_product_picks=[])
    cands = [
        {
            "product_id": "bad",
            "name": "缺保额",
            "match_reason": "x",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/x",
            "sum_assured": None,
            "premium": "HKD 1",
            "excerpt_date": "2026-10-01",
        },
        {
            "product_id": "good",
            "name": "齐全",
            "match_reason": "y",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/y",
            "sum_assured": "HKD 9",
            "premium": "HKD 1",
            "excerpt_date": "2026-10-01",
        },
    ]
    mid = hydrate_concrete_picks_from_candidates(payload, cands, max_picks=3)
    out = filter_picks_requiring_three_fields(mid)
    ids = [p.product_id for p in out.concrete_product_picks]
    assert ids == ["good"]
```

- [ ] **Step 2: Run — expect fail**

Run: `cd backend && uv run python -m pytest tests/test_report_products.py -k filter -v --basetemp=.pytest_basetemp`

Expected: FAIL (function missing)

- [ ] **Step 3: Implement filter**

```python
# In backend/app/report_products.py

def _present(value: str | None) -> bool:
    return value is not None and str(value).strip() != ""


def filter_picks_requiring_three_fields(payload: ReportPayload) -> ReportPayload:
    kept = [
        p
        for p in payload.concrete_product_picks
        if _present(p.sum_assured) and _present(p.premium) and _present(p.excerpt_date)
    ]
    return payload.model_copy(update={"concrete_product_picks": kept})
```

- [ ] **Step 4: Run — expect pass**

Run: `cd backend && uv run python -m pytest tests/test_report_products.py -v --basetemp=.pytest_basetemp`

Expected: all PASS

- [ ] **Step 5: Commit** (only if operator asked)

```bash
git add backend/app/report_products.py backend/tests/test_report_products.py
git commit -m "feat(report): drop picks missing sum_assured, premium, or excerpt_date"
```

---

### Task 2: Wire filter on report generate path

**Files:**
- Modify: `backend/app/routers/conversations.py` (report generate block ~880–886)

- [ ] **Step 1: Import and call after hydrate**

```python
from app.report_products import (
    enrich_product_picks_with_sources,
    filter_picks_requiring_three_fields,
    hydrate_concrete_picks_from_candidates,
    sanitize_concrete_product_picks,
)
```

After:

```python
payload = hydrate_concrete_picks_from_candidates(payload, candidates)
```

add:

```python
payload = filter_picks_requiring_three_fields(payload)
```

Also call `filter_picks_requiring_three_fields` when the `not candidates` branch clears picks (no-op) — only required on the `else` branch where picks may exist. If picks can exist with empty candidates, still run once on the payload before `enforce_report_output_locale`.

Safest: after the whole if/else that mutates picks, always:

```python
payload = filter_picks_requiring_three_fields(payload)
```

immediately before `enforce_report_output_locale(...)`.

- [ ] **Step 2: Run report_products tests + any report API smoke that exists**

Run: `cd backend && uv run python -m pytest tests/test_report_products.py -v --basetemp=.pytest_basetemp`

Expected: PASS

- [ ] **Step 3: Commit** (only if operator asked)

```bash
git add backend/app/routers/conversations.py docs/superpowers/specs/2026-10-23-us2-missing-fields-gate-design.md docs/superpowers/plans/2026-10-23-us2-missing-fields-gate.md
git commit -m "feat(report): apply three-field gate before locale enforce"
```

---

## Spec coverage self-check

| Spec | Task |
|------|------|
| filter helper + missing = blank | Task 1 |
| after hydrate | Task 2 |
| AC-1–3 unit tests | Task 1 |
| AC-4 structured (hydrate then filter) | Task 1 |
| No narrative scrub / no US-3 | Out of scope |

## Placeholder / consistency self-check

- Field names match US-1/US-5
- No TBD

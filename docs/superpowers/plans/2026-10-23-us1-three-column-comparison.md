# US-1 Three-Column Product Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Customer report product comparison shows exactly three columns — 保额、保费、日期 (zh-CN) — replacing the card list.

**Architecture:** Extend `ReportProductPick` with optional library fields; enrich picks from candidate map / Product row; replace frontend picks cards with a three-column table. Do not filter missing/expired rows (US-2/3). Do not change chat or disclaimer.

**Tech Stack:** FastAPI/Pydantic, Next.js report page, next-intl messages, pytest (and existing frontend test tooling if present; otherwise component assertions via Playwright smoke or a small React test if the repo already has one).

**Spec:** `docs/superpowers/specs/2026-10-23-us1-three-column-comparison-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Modify `backend/app/schemas.py` | Add three optional fields on `ReportProductPick` |
| Modify `backend/app/report_products.py` | Copy three fields in `enrich_product_picks_with_sources` (and hydrate path) |
| Modify `backend/app/routers/conversations.py` and/or retrieval candidate builder | Ensure candidate dicts include `sum_assured`, `premium`, `excerpt_date` from `Product` when available |
| Modify `backend/tests/test_report_products.py` | Enrich assertions |
| Modify `frontend/lib/types.ts` | Optional three fields on picks |
| Modify `frontend/messages/{zh-CN,zh-TW,en}.json` | Column header strings |
| Modify `frontend/app/[locale]/(app)/conversations/[id]/report/page.tsx` | Table UI; remove card columns |
| Optional: frontend e2e or unit if present | Headers-only assertion |

---

### Task 1: Schema + enrich three fields

**Files:**
- Modify: `backend/app/schemas.py` (`ReportProductPick`)
- Modify: `backend/app/report_products.py`
- Modify: candidate construction used before `enrich_product_picks_with_sources` in `conversations.py` / retriever output — wherever `source_url` / `name` are put on candidates, also put the three Product fields (isoformat for `excerpt_date`)
- Test: `backend/tests/test_report_products.py`

- [ ] **Step 1: Write failing enrich test**

```python
# Append to backend/tests/test_report_products.py
from app.schemas import ReportPayload, ReportProductPick
from app.report_products import enrich_product_picks_with_sources


def test_enrich_copies_sum_premium_excerpt_from_candidate() -> None:
    payload = ReportPayload(
        concrete_product_picks=[
            ReportProductPick(product_id="p1", name="旧名", rationale="", source_url="")
        ]
    )
    cmap = {
        "p1": {
            "name": "产品甲",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/x",
            "match_reason": "match",
            "sum_assured": "HKD 1,000,000",
            "premium": "HKD 500",
            "excerpt_date": "2026-10-01",
        }
    }
    out = enrich_product_picks_with_sources(payload, cmap)
    pick = out.concrete_product_picks[0]
    assert pick.sum_assured == "HKD 1,000,000"
    assert pick.premium == "HKD 500"
    assert pick.excerpt_date == "2026-10-01"
```

- [ ] **Step 2: Run — expect fail**

Run: `cd backend && uv run python -m pytest tests/test_report_products.py::test_enrich_copies_sum_premium_excerpt_from_candidate -v --basetemp=.pytest_basetemp`

Expected: FAIL (fields missing on model or always None)

- [ ] **Step 3: Implement schema + enrich**

On `ReportProductPick` in `schemas.py`:

```python
sum_assured: str | None = None
premium: str | None = None
excerpt_date: str | None = None
```

In `enrich_product_picks_with_sources`, when building each `ReportProductPick`, also set:

```python
sum_assured=(cand.get("sum_assured") if cand.get("sum_assured") is not None else p.sum_assured),
premium=(cand.get("premium") if cand.get("premium") is not None else p.premium),
excerpt_date=(cand.get("excerpt_date") if cand.get("excerpt_date") is not None else p.excerpt_date),
```

Prefer: if candidate has key, use it (including explicit None); else keep pick’s value. Simpler acceptable version: always take from cand with `cand.get("sum_assured") or p.sum_assured` only if empty-string should not wipe — for US-1, using:

```python
sum_assured=str(cand["sum_assured"]) if "sum_assured" in cand and cand["sum_assured"] is not None else (p.sum_assured if "sum_assured" not in cand else None),
```

Keep it readable: 

```python
def _opt_str(cand: dict, key: str, fallback: str | None) -> str | None:
    if key not in cand:
        return fallback
    v = cand.get(key)
    if v is None:
        return None
    return str(v)
```

Also update `hydrate_concrete_picks_from_candidates` append to pass through any three fields present on `c`.

Wire candidate maps: find where retrieval builds dicts with `product_id`, `name`, `source_url` and add:

```python
"sum_assured": product.sum_assured,
"premium": product.premium,
"excerpt_date": product.excerpt_date.isoformat() if product.excerpt_date else None,
```

- [ ] **Step 4: Run test — expect pass**

Run: `cd backend && uv run python -m pytest tests/test_report_products.py -v --basetemp=.pytest_basetemp`

Expected: PASS (including new test)

- [ ] **Step 5: Commit** (only if operator asked)

```bash
git add backend/app/schemas.py backend/app/report_products.py backend/tests/test_report_products.py
# plus any candidate-builder file touched
git commit -m "feat(report): enrich product picks with sum_assured, premium, excerpt_date"
```

---

### Task 2: Frontend three-column table

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/messages/zh-CN.json`, `zh-TW.json`, `en.json`
- Modify: `frontend/app/[locale]/(app)/conversations/[id]/report/page.tsx`

- [ ] **Step 1: Add i18n keys**

In each locale file under the report namespace (same object as `picksTitle`):

zh-CN:
```json
"compareColSum": "保额",
"compareColPremium": "保费",
"compareColDate": "日期"
```

zh-TW:
```json
"compareColSum": "保額",
"compareColPremium": "保費",
"compareColDate": "日期"
```

en:
```json
"compareColSum": "Sum assured",
"compareColPremium": "Premium",
"compareColDate": "Date"
```

- [ ] **Step 2: Extend TS types**

```typescript
concrete_product_picks?: {
  product_id: string;
  name: string;
  rationale: string;
  source_url?: string;
  sum_assured?: string | null;
  premium?: string | null;
  excerpt_date?: string | null;
}[];
```

- [ ] **Step 3: Replace card list with table in report page**

Where `body.concrete_product_picks.map` currently renders cards, replace with:

```tsx
<table className="w-full text-sm border-collapse">
  <thead>
    <tr>
      <th className="border-b py-2 text-left font-medium">{tr("compareColSum")}</th>
      <th className="border-b py-2 text-left font-medium">{tr("compareColPremium")}</th>
      <th className="border-b py-2 text-left font-medium">{tr("compareColDate")}</th>
    </tr>
  </thead>
  <tbody>
    {body.concrete_product_picks.map((p) => (
      <tr key={p.product_id}>
        <td className="border-b py-2">{p.sum_assured ?? ""}</td>
        <td className="border-b py-2">{p.premium ?? ""}</td>
        <td className="border-b py-2">{p.excerpt_date ?? ""}</td>
      </tr>
    ))}
  </tbody>
</table>
```

Remove from this section: name heading, refLabel/product_id, rationale paragraph, source_url link, knowledge library link. Keep section title (`picksTitle`) or rename only if needed — US-1 does not require renaming the section.

- [ ] **Step 4: Verify headers (manual or e2e)**

If `frontend/e2e` can open a report with picks fixtures, assert three `th` texts for zh-CN. Otherwise document manual check:

1. Generate or load a report with at least one pick in zh-CN.
2. Confirm table headers are exactly 保额、保费、日期.
3. Confirm no column for 名称 / 类别 / 链接.

Optional focused unit: extract a tiny pure helper `comparisonHeaders(locale)` only if the team already unit-tests i18n — YAGNI otherwise; rely on message keys + page markup.

- [ ] **Step 5: Commit** (only if operator asked)

```bash
git add frontend/lib/types.ts frontend/messages/zh-CN.json frontend/messages/zh-TW.json frontend/messages/en.json frontend/app/[locale]/(app)/conversations/[id]/report/page.tsx
git commit -m "feat(report): show product comparison as three-column table"
```

---

### Task 3: Regression — AC-3 no fourth column in markup

**Files:**
- Modify or create a small test if e2e exists; else add a comment-backed checklist in plan completion only.

Prefer: extend `frontend/e2e/smoke.spec.ts` only if it already covers report; do not invent a heavy e2e suite.

Minimal backend-facing lock (optional): none required beyond Task 1.

- [ ] **Step 1: Grep report page for removed card fields in the picks section**

Confirm `page.tsx` picks section no longer renders `p.name` as a column/header, `tr("refLabel")`, `p.rationale`, `tr("dataSource")`, or `tr("viewInLibrary")` inside the comparison block.

- [ ] **Step 2: Run backend report_products tests again**

Run: `cd backend && uv run python -m pytest tests/test_report_products.py -v --basetemp=.pytest_basetemp`

Expected: PASS

- [ ] **Step 3: Commit docs** (only if operator asked)

```bash
git add docs/superpowers/specs/2026-10-23-us1-three-column-comparison-design.md docs/superpowers/plans/2026-10-23-us1-three-column-comparison.md
git commit -m "docs: US-1 three-column comparison spec and plan"
```

---

## Spec coverage self-check

| Spec | Task |
|------|------|
| Schema three optional fields | Task 1 |
| Enrich from library/candidates | Task 1 |
| Frontend table three headers zh-CN 保额/保费/日期 | Task 2 |
| No name/category/link as columns | Task 2–3 |
| US-2/3/4 out of scope | Not implemented |

## Placeholder / consistency self-check

- Field names match Product / US-5: `sum_assured`, `premium`, `excerpt_date`
- zh-CN headers exact characters from US-1 story
- No TBD

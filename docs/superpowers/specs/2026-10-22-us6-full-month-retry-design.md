---
artifact: design-spec
version: "1.0"
created: 2026-10-22
status: draft
product: hkia-assistant
task_row: US-6
source_stories: docs/2026-10-22-用户故事-保额保费摘录日期.md
depends_on: docs/superpowers/specs/2026-10-22-monthly-sum-premium-excerpt-ingest-design.md
---

# Design: US-6 失败后整月再跑（测试锁行为）

## Goal

Lock the US-5 batch behavior that already satisfies US-6: after a mid-run failure, the next monthly start runs the full URL list again. No resume cursor. Operator does not hand-edit a breakpoint. No product-logic change to the runner or CLI in this row.

## Decisions

- Approach: add acceptance tests only in `backend/tests/test_monthly_product_fields.py`.
- Do not change `monthly_product_fields.py` or `monthly_product_fields_cli.py` unless a test proves a real gap (then stop and reopen design).
- Do not add a resume cursor, progress board, or SLO.

## Architecture (unchanged)

Existing behavior under test:

1. `run_monthly_product_fields` takes the full `product_urls` sequence each call. It does not read a stored “next product” cursor from `DataUpdateJob` or elsewhere.
2. On `fetch` exception, the job is `failed`. Partial writes from earlier URLs in that transaction may remain; the next call still receives the full list and overwrites by `official_url` (US-5 design).
3. CLI `_already_succeeded_this_month` only seals on success with `updated_count > 0`. A `failed` job never seals the month.

## Tests to add

### T1 — Mid-fail then full-list second run (AC-1)

**Given** two allowlisted product URLs seeded in DB  
**When** first `run_monthly_product_fields` uses a `fetch` that succeeds for URL1 then raises on URL2  
**Then** first job `status == "failed"`  
**And** second `run_monthly_product_fields` is called with the **same full two-URL list** and a fetch that succeeds for both  
**Then** second job `status == "success"` and both products have `excerpt_date` for the run month  
**And** no row in `data_update_jobs.detail_json` (or any new table) stores a resume / next-product cursor key such as `resume_from`, `next_url`, `cursor`

### T2 — Failed job does not require hand breakpoint (AC-2)

**Given** a `failed` `monthly_product_fields` job already in DB for the Hong Kong month  
**When** the CLI seal helper `_already_succeeded_this_month` is evaluated for that month  
**Then** it returns `False` (month not sealed)  
so the operator can start the next run without editing progress state.

Prefer calling the helper directly with a seeded failed job; do not require live HTTP.

## Out of scope

- US-1–5, US-7 behavior changes
- Changing extractors, allowlist, or field schema
- Operator UI / progress board
- Live China Life network run

## Acceptance map

| US-6 AC | Evidence |
|---------|----------|
| AC-1 整月再跑 | T1 |
| AC-2 不用手补断点 | T2 |

## Self-review

- No TBD.
- Scope is tests-only; matches operator choice “1”.
- Cursor absence asserted explicitly so a future “helpful” resume flag would fail the suite.

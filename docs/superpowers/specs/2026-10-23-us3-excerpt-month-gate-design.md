---
artifact: design-spec
version: "1.0"
created: 2026-10-23
status: draft
product: hkia-assistant
task_row: US-3
source_stories: docs/2026-10-22-用户故事-保额保费摘录日期.md
---

# Design: US-3 过月产品不进结构化报告引用

## Goal

Products whose `excerpt_date` month is earlier than the report-generation calendar month in `Asia/Hong_Kong`, or whose `excerpt_date` cannot be mapped to a calendar month, must not appear in `concrete_product_picks`. Same-month excerpts are not blocked for expiry. No day-count freshness. No narrative scrub in this row.

## Decisions

- Separate helper from US-2: `filter_picks_current_excerpt_month(payload, *, now=None)`.
- Report month = year/month of `(now or datetime.now(ZoneInfo("Asia/Hong_Kong")))`.
- Parse `excerpt_date` as ISO `YYYY-MM-DD` or `YYYY-MM` only; anything else (including unparseable non-empty strings) → drop (AC-3). Empty already handled by US-2 three-field gate.
- Keep only when excerpt year-month == report year-month.
- AC-1 "其他位置" for this row = structured picks only (aligned with US-2).
- Call order on report generate path: after each `filter_picks_requiring_three_fields` call, run the month filter (hydrate path once, post-locale once).

## Architecture

1. Add `filter_picks_current_excerpt_month` in `backend/app/report_products.py`.
2. Inject `now` in tests for AC-4 (month boundary).
3. Wire in `backend/app/routers/conversations.py` immediately after both existing three-field filter call sites.
4. Unit tests in `backend/tests/test_report_products.py` for AC-1–4 structured cases.

## Out of scope

- Narrative / attachment full-text scrub
- Retrieval or SQL pre-filter
- Day-based expiry
- US-4 DB consistency
- UI changes
- Changing US-2 three-field semantics

## Acceptance map

| AC | Evidence |
|----|----------|
| AC-1 earlier month | Unit: pick with prior-month ISO date dropped from picks |
| AC-2 same month | Unit: same-month pick kept |
| AC-3 unparseable | Unit: garbage `excerpt_date` dropped |
| AC-4 boundary | Unit: `now` fixed just after HK month boundary |

## Self-review

- No TBD.
- Structured-only AC-1 locked with operator.
- Filter order locked: after US-2 three-field gate, twice (pre- and post-locale).
- Parse rule explicit: `YYYY-MM-DD` / `YYYY-MM` only.

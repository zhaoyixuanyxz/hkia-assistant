---
artifact: design-spec
version: "1.0"
created: 2026-10-23
status: draft
product: hkia-assistant
task_row: US-2
source_stories: docs/2026-10-22-用户故事-保额保费摘录日期.md
---

# Design: US-2 缺字段产品不进结构化报告引用

## Goal

Products missing `sum_assured`, `premium`, or `excerpt_date` must not appear in `concrete_product_picks` on the customer report (the three-column comparison). They must not be re-inserted by hydrate. Narrative prose is not scrubbed in this row.

## Decisions

- Gate after sanitize → enrich → hydrate (last structured filter before locale enforce / persist).
- Missing = `None` or blank/whitespace-only string after strip.
- AC-4 for this row = no structured product reference (picks list). No full-text scrub of insights.
- US-3 (month expiry) out of scope.

## Architecture

1. Add `filter_picks_requiring_three_fields(payload: ReportPayload) -> ReportPayload` in `backend/app/report_products.py`.
2. Keep a pick only if all three of `sum_assured`, `premium`, `excerpt_date` are non-empty after strip.
3. Call it in report generate path in `conversations.py` after `hydrate_concrete_picks_from_candidates` (and after enrich if hydrate is skipped when picks already present — always run once on the final picks list before saving).
4. Unit tests: drop pick missing sum; drop missing premium; drop missing excerpt_date; keep pick with all three; hydrate cannot leave a missing-field product in the final list when filter runs last.

## Out of scope

- Expiry by calendar month (US-3)
- Scrubbing product names from free text
- Changing the three-column UI
- Changing ingest (US-5/6)

## Acceptance map

| AC | Evidence |
|----|----------|
| AC-1–3 | Unit tests drop picks missing each field |
| AC-4 (structured) | Final `concrete_product_picks` has no blocked product_id; hydrate-then-filter test |

## Self-review

- No TBD.
- Scope matches operator choice (structured only).
- Filter order locked: after hydrate.

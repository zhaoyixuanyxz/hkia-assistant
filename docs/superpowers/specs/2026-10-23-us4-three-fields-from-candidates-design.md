---
artifact: design-spec
version: "1.0"
created: 2026-10-23
status: draft
product: hkia-assistant
task_row: US-4
source_stories: docs/2026-10-22-用户故事-保额保费摘录日期.md
---

# Design: US-4 三列只来自检索候选（产品库快照）

## Goal

Report comparison columns `sum_assured`, `premium`, and `excerpt_date` must match the current retrieval candidate snapshot for that `product_id`. The model must not invent or keep invented values for these three fields. Report generation must not fetch product pages to fill them. Freshness of the product DB itself is out of scope (login-triggered update, not this row).

## Decisions

- Source of truth for this row = retrieval `candidates` / `candidate_map` (DB fields already on candidates), not a second DB round-trip at generate time.
- Change `enrich_product_picks_with_sources` so the three fields are taken **only** from the candidate entry (missing key or null → `None`). Never fall back to the pick’s model-supplied values.
- Keep existing fallback behavior for `name` / `rationale` / `source_url`.
- After `enforce_report_output_locale`, run `enrich_product_picks_with_sources` again with the same `candidate_map`, then re-run US-2 and US-3 filters (so EN rewrite cannot leave invented or empty three-fields past the gates incorrectly — empty after re-enrich still drops via US-2).
- Lift `candidate_map` construction above the `if not candidates` branch (empty map when no candidates).
- No new web fetch on the report path. No MCP. No login-triggered ingest in this row.

## Architecture

1. Update `_opt_str` usage for the three fields in enrich (or a dedicated helper) so pick fallback is unused for those keys.
2. Wire post-locale enrich in `conversations.py`.
3. Unit tests: model values overwritten by candidate; candidate missing field → `None` despite model fill.

## Out of scope

- Login-triggered product field refresh
- Re-querying Product table inside generate_report
- Narrative scrub
- Changing US-2 / US-3 semantics (only call order: enrich → three-field → month after locale)
- UI changes

## Acceptance map

| AC | Evidence |
|----|----------|
| AC-1 match library snapshot | Unit: enrich forces candidate values over wrong model values |
| AC-2 no model fill | Unit: candidate lacks sum/premium → result None, not model string |
| AC-3 no live fetch | No new fetch in report path; design + code review |

## Self-review

- No TBD.
- Operator locked: always candidate wins; candidate snapshot not live DB re-read; post-locale re-enrich.
- Login freshness explicitly out of scope.

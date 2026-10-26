---
artifact: design-spec
version: "1.0"
created: 2026-10-23
status: draft
product: hkia-assistant
task_row: US-1
source_stories: docs/2026-10-22-用户故事-保额保费摘录日期.md
source_prd: docs/2026-10-22-PRD-保额保费摘录日期.md
---

# Design: US-1 客户产品对比只有三列

## Goal

In the customer-facing report, replace the concrete-product card list with a three-column comparison table. Column headers (Simplified Chinese acceptance path): 保额、保费、日期. No fourth comparison column for name, category, or link.

## Decisions

- Replace the product card block with a table (operator choice).
- Keep `concrete_product_picks` as the row source; enrich each pick with `sum_assured`, `premium`, `excerpt_date` from the product library.
- US-1 only locks column count and header names. Empty cells are allowed. Gate missing/expired rows in US-2/US-3. Value equality with the library is US-4.
- Do not change chat UI, disclaimer, or「第一次会见拿出 3 个方案」.

## Architecture

1. **Backend schema** — Extend `ReportProductPick` with optional `sum_assured: str | None`, `premium: str | None`, `excerpt_date: str | None` (ISO date string when set). Existing `name` / `rationale` / `source_url` may remain on the model for other uses but must not appear as comparison columns.
2. **Enrich** — In `enrich_product_picks_with_sources` (or adjacent helper), load `Product` by `product_id` and copy the three fields. Missing library values → `None` / empty string (rows still appear in US-1).
3. **Frontend** — Report page section for picks: render a `<table>` with exactly three `<th>` headers. Locale headers:
   - `zh-CN`: 保额、保费、日期
   - `zh-TW`: 保額、保費、日期
   - `en`: Sum assured、Premium、Date  
   Acceptance evidence for US-1 uses the zh-CN headers.
4. **Out of comparison UI** — Do not show name, product_id, rationale, source link, or library link as table columns. Prefer removing those from this section entirely for the customer comparison block.

## Out of scope

- US-2 / US-3 filtering
- US-4 asserting cell values match DB in acceptance of this row (enrich still fills from DB for later stories)
- Changing monthly ingest (US-5/6)
- Visual redesign beyond a plain three-column table

## Acceptance map

| US-1 AC | Evidence |
|---------|----------|
| AC-1 only three columns | Frontend/integration: comparison table has exactly three columns |
| AC-2 header names 保额、保费、日期 | zh-CN headers match exactly |
| AC-3 no fourth column for name/category/link | Those fields not rendered as `<th>` / comparison columns |

## Testing notes

- Unit/API: enriched pick JSON includes the three keys when Product has values.
- UI or component test: with sample picks, table headers are exactly the three zh-CN labels (or assert via i18n keys that resolve to them); assert absence of a column header for name / category / link.

## Self-review

- No TBD.
- Scope matches US-1 only.
- Column titles locked; no competing “product name” column in the comparison table.

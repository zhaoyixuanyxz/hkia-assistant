---
artifact: design-spec
version: "1.0"
created: 2026-10-23
status: draft
product: hkia-assistant
task_row: US-7
source_stories: docs/2026-10-22-用户故事-保额保费摘录日期.md
---

# Design: US-7 对外说法 / 免责声明 / 四条边界锁测

## Goal

Prove that this iteration did not change the locked external pitch, report disclaimers, or China Life Overseas–only product URL boundary. Deliver regression tests only — no product copy or feature changes.

## Decisions

- Deliverable = new test module `backend/tests/test_us7_messaging_boundaries.py`.
- AC-1: assert docs PRD still contains exact string `第一次会见拿出 3 个方案` (string lives in docs, not app code).
- AC-2: assert `STANDARD_DISCLAIMERS` for `zh-CN` / `zh-TW` / `en` equal the current committed full texts (embed expected strings in the test).
- AC-3: lock existing hard constraints — `allowed_product_url` accepts only `chinalife.com.hk` product deep links; reject other hosts / non-product paths; zh-CN disclaimer still contains the existing “不构成持牌…建议” clause. Do not add new underwriting / signing / premium-collection features.
- Out of scope: changing the pitch after three fields are in the DB; disclaimer layout; inventing new boundary constants.

## Architecture

1. Add tests only under `backend/tests/`.
2. Read PRD via path relative to repo root (resolve from `backend/tests` → parents).
3. Import `STANDARD_DISCLAIMERS` from `app.compliance` and `allowed_product_url` from `app.product_fields_extract`.

## Acceptance map

| AC | Evidence |
|----|----------|
| AC-1 pitch | Doc contains exact phrase |
| AC-2 disclaimer | Three-locale equality tests |
| AC-3 boundaries | URL allow/deny + disclaimer clause |

## Self-review

- No TBD.
- No product code changes in this row.
- Pitch locked via docs (operator choice).

# US-4 Three Fields From Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Force report pick `sum_assured` / `premium` / `excerpt_date` to come only from retrieval candidates; never keep model-invented values; re-enrich after locale so EN rewrite can be restored from candidates.

**Architecture:** Change `enrich_product_picks_with_sources` so the three fields ignore pick fallbacks. Lift `candidate_map` in `conversations.py` and call enrich again after `enforce_report_output_locale`, before US-2/US-3. No live DB re-read, no fetch.

**Tech Stack:** FastAPI, Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-us4-three-fields-from-candidates-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Modify `backend/app/report_products.py` | Candidate-only three fields in enrich |
| Modify `backend/app/routers/conversations.py` | candidate_map hoist + post-locale enrich |
| Modify `backend/tests/test_report_products.py` | AC-1/AC-2 unit tests |

---

### Task 1: Enrich overwrites model three-fields

**Files:**
- Modify: `backend/app/report_products.py` (`enrich_product_picks_with_sources`)
- Test: `backend/tests/test_report_products.py`

- [ ] **Step 1: Write failing tests**

```python
def test_enrich_overwrites_model_three_fields_from_candidate() -> None:
    payload = ReportPayload(
        concrete_product_picks=[
            ReportProductPick(
                product_id="p1",
                name="n",
                rationale="r",
                sum_assured="MODEL_SUM",
                premium="MODEL_PREM",
                excerpt_date="2099-01-01",
            )
        ]
    )
    cmap = {
        "p1": {
            "name": "库名",
            "match_reason": "m",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/x",
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


def test_enrich_does_not_keep_model_fill_when_candidate_missing_fields() -> None:
    payload = ReportPayload(
        concrete_product_picks=[
            ReportProductPick(
                product_id="p1",
                name="n",
                rationale="r",
                sum_assured="MODEL_SUM",
                premium="MODEL_PREM",
                excerpt_date="2026-10-01",
            )
        ]
    )
    cmap = {
        "p1": {
            "name": "库名",
            "match_reason": "m",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/x",
            "sum_assured": None,
            "premium": None,
            "excerpt_date": "2026-10-01",
        }
    }
    out = enrich_product_picks_with_sources(payload, cmap)
    pick = out.concrete_product_picks[0]
    assert pick.sum_assured is None
    assert pick.premium is None
    assert pick.excerpt_date == "2026-10-01"
```

Also update `test_enrich_copies_sum_premium_excerpt_from_candidate` if needed (should still pass).

- [ ] **Step 2: Run — expect fail on overwrite test**

```
cd backend
uv run python -m pytest tests/test_report_products.py -k enrich -v --basetemp=.pytest_basetemp
```

Expected: `test_enrich_overwrites_model_three_fields_from_candidate` FAIL if candidate key missing would fallback — with keys present current code may already overwrite; force FAIL by also covering candidate **without** keys:

If current `_opt_str(cand, key, p.sum_assured)` already overwrites when key present, Step 1's first test may PASS early. Prefer this additional case for RED:

```python
def test_enrich_ignores_model_when_candidate_omits_three_field_keys() -> None:
    payload = ReportPayload(
        concrete_product_picks=[
            ReportProductPick(
                product_id="p1",
                name="n",
                rationale="r",
                sum_assured="MODEL_SUM",
                premium="MODEL_PREM",
                excerpt_date="2099-01-01",
            )
        ]
    )
    cmap = {
        "p1": {
            "name": "库名",
            "match_reason": "m",
            "source_url": "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/x",
            # no sum_assured / premium / excerpt_date keys
        }
    }
    out = enrich_product_picks_with_sources(payload, cmap)
    pick = out.concrete_product_picks[0]
    assert pick.sum_assured is None
    assert pick.premium is None
    assert pick.excerpt_date is None
```

Expected RED: current code falls back to MODEL_*.

- [ ] **Step 3: Implement candidate-only three fields**

```python
def _cand_field(cand: dict, key: str) -> str | None:
    if key not in cand:
        return None
    v = cand.get(key)
    if v is None:
        return None
    text = str(v).strip()
    return text or None


def enrich_product_picks_with_sources(
    payload: ReportPayload, candidate_map: dict[str, dict]
) -> ReportPayload:
    picks: list[ReportProductPick] = []
    for p in payload.concrete_product_picks:
        cand = candidate_map.get(p.product_id, {})
        rationale = p.rationale or str(cand.get("match_reason", ""))
        source_url = p.source_url or str(cand.get("source_url", ""))
        picks.append(
            ReportProductPick(
                product_id=p.product_id,
                name=p.name or str(cand.get("name", "")),
                rationale=rationale,
                source_url=source_url,
                sum_assured=_cand_field(cand, "sum_assured"),
                premium=_cand_field(cand, "premium"),
                excerpt_date=_cand_field(cand, "excerpt_date"),
            )
        )
    return payload.model_copy(update={"concrete_product_picks": picks})
```

Keep `_opt_str` for hydrate (still uses fallback for absent keys on hydrate path — hydrate builds from cand only already).

- [ ] **Step 4: Run — expect pass**

```
cd backend
uv run python -m pytest tests/test_report_products.py -v --basetemp=.pytest_basetemp
```

Expected: all PASS

- [ ] **Step 5: Commit** (only if operator asked)

```bash
git add backend/app/report_products.py backend/tests/test_report_products.py
git commit -m "feat(report): take sum/premium/excerpt only from candidates"
```

---

### Task 2: Post-locale re-enrich on generate path

**Files:**
- Modify: `backend/app/routers/conversations.py` (~861–896)

- [ ] **Step 1: Hoist candidate_map and re-enrich after locale**

```python
candidates = rout.get("candidates") or []
allowed_ids = {str(c.get("product_id")) for c in candidates if c.get("product_id")}
candidate_map = {
    str(c.get("product_id")): c for c in candidates if c.get("product_id")
}
# ... validate payload ...

if not candidates:
    # ... clear picks notice ...
else:
    payload = sanitize_concrete_product_picks(payload, allowed_ids)
    payload = enrich_product_picks_with_sources(payload, candidate_map)
    payload = hydrate_concrete_picks_from_candidates(payload, candidates)

payload = filter_picks_requiring_three_fields(payload)
payload = filter_picks_current_excerpt_month(payload)
payload = enforce_report_output_locale(
    payload, survey_answers, locale=loc, llm=llm
)
# Restore three fields from candidates after EN rewrite may strip them.
payload = enrich_product_picks_with_sources(payload, candidate_map)
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
git add backend/app/routers/conversations.py docs/superpowers/specs/2026-10-23-us4-three-fields-from-candidates-design.md docs/superpowers/plans/2026-10-23-us4-three-fields-from-candidates.md
git commit -m "feat(report): re-enrich three fields from candidates after locale"
```

---

## Spec coverage self-check

| Spec | Task |
|------|------|
| Candidate-only three fields in enrich | Task 1 |
| Post-locale enrich then US-2/US-3 | Task 2 |
| AC-1/AC-2 unit tests | Task 1 |
| No fetch / no login ingest | Out of scope |

## Placeholder / consistency self-check

- Field names match US-1/2/3/5
- No TBD

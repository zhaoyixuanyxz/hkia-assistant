# US-6 Full-Month Retry (Test Lock) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two tests that lock US-6: after a mid-batch failure, the next run uses the full URL list with no resume cursor, and a failed job does not seal the month.

**Architecture:** Tests-only. No changes to `monthly_product_fields.py` or `monthly_product_fields_cli.py` unless a new test fails against current code — then stop and reopen the design (do not silently add a cursor).

**Tech Stack:** pytest, SQLAlchemy 2.0, existing injectable `fetch`, CLI helper `_already_succeeded_this_month`.

**Spec:** `docs/superpowers/specs/2026-10-22-us6-full-month-retry-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Modify `backend/tests/test_monthly_product_fields.py` | Add T1 and T2 for US-6 |
| Do not modify | `backend/app/monthly_product_fields.py`, `backend/app/jobs/monthly_product_fields_cli.py` |

---

### Task 1: T1 — Mid-fail then full-list second run (AC-1)

**Files:**
- Modify: `backend/tests/test_monthly_product_fields.py`
- Test: same file

- [ ] **Step 1: Append the failing-or-locking test**

Add to `backend/tests/test_monthly_product_fields.py` (reuse `_seed_product`, `FIXTURES`, `HK`, `api_client` pattern):

```python
def test_us6_mid_fail_then_full_list_second_run(api_client: TestClient) -> None:
    """AC-1: next start after mid-fail is full batch, not resume-from-failed-url."""
    from app.models import DataUpdateJob

    url1 = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/plan-a"
    url2 = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/plan-b"
    _seed_product(url1, pid="prod-us6-a")
    _seed_product(url2, pid="prod-us6-b")
    html = (FIXTURES / "single_numbers.html").read_text(encoding="utf-8")
    urls = [url1, url2]
    when = datetime(2026, 10, 15, 12, 0, tzinfo=HK)

    calls: list[str] = []

    def fetch_fail_second(u: str) -> str:
        calls.append(u)
        if u == url2:
            raise TimeoutError("network down on second product")
        return html

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job1 = run_monthly_product_fields(
            db=s, product_urls=urls, fetch=fetch_fail_second, now=when
        )
        s.commit()
        assert job1.status == "failed"
        assert "resume_from" not in (job1.detail_json or {})
        assert "next_url" not in (job1.detail_json or {})
        assert "cursor" not in (job1.detail_json or {})

        def fetch_ok(u: str) -> str:
            calls.append(u)
            return html

        job2 = run_monthly_product_fields(
            db=s, product_urls=urls, fetch=fetch_ok, now=when
        )
        s.commit()
        assert job2.status == "success"
        # Second run must hit the full list (both URLs), not only url2
        second_run_urls = calls[calls.index(url2) + 1 :]  # after the failing call
        assert url1 in second_run_urls and url2 in second_run_urls

        for pid in ("prod-us6-a", "prod-us6-b"):
            row = s.get(Product, pid)
            assert row is not None
            assert row.excerpt_date == date(2026, 10, 1)

        # No job detail ever carries a resume cursor key
        jobs = s.scalars(select(DataUpdateJob).where(DataUpdateJob.job_type == "monthly_product_fields")).all()
        for j in jobs:
            detail = j.detail_json or {}
            assert "resume_from" not in detail
            assert "next_url" not in detail
            assert "cursor" not in detail
    finally:
        s.close()
```

Import `DataUpdateJob` at top of file if preferred over inline import; match file style (`select` already imported).

- [ ] **Step 2: Run the new test**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && uv run python -m pytest tests/test_monthly_product_fields.py::test_us6_mid_fail_then_full_list_second_run -v --basetemp=.pytest_basetemp`

Expected: **PASS** (locks existing US-5 behavior).  
If **FAIL**: stop. Do not add a resume cursor. Report DONE_WITH_CONCERNS / BLOCKED and reopen design.

- [ ] **Step 3: Commit** (only if operator asked)

```bash
git add backend/tests/test_monthly_product_fields.py
git commit -m "test(us6): lock full-list retry after mid-batch fetch failure"
```

---

### Task 2: T2 — Failed job does not seal the month (AC-2)

**Files:**
- Modify: `backend/tests/test_monthly_product_fields.py`

- [ ] **Step 1: Append seal helper test**

```python
def test_us6_failed_job_does_not_seal_month(api_client: TestClient) -> None:
    """AC-2: operator can start next run without hand-editing a breakpoint."""
    from app.jobs.monthly_product_fields_cli import _already_succeeded_this_month
    from app.models import DataUpdateJob
    from app.monthly_product_fields import JOB_TYPE

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        month_iso = "2026-10-01"
        s.add(
            DataUpdateJob(
                job_type=JOB_TYPE,
                status="failed",
                error_message="network down",
                detail_json={
                    "updated_count": 1,
                    "skipped_count": 0,
                    "no_single_number_count": 0,
                    "excerpt_month": month_iso,
                },
            )
        )
        s.commit()
        assert _already_succeeded_this_month(s, month_iso) is False
    finally:
        s.close()
```

- [ ] **Step 2: Run T2 + full related suite**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && uv run python -m pytest tests/test_monthly_product_fields.py tests/test_product_fields_extract.py -v --basetemp=.pytest_basetemp`

Expected: all PASS (14 tests if both US-6 tests added to the previous 12).

If T2 FAIL: stop; do not weaken the seal helper without design reopen.

- [ ] **Step 3: Commit** (only if operator asked)

```bash
git add backend/tests/test_monthly_product_fields.py docs/superpowers/specs/2026-10-22-us6-full-month-retry-design.md docs/superpowers/plans/2026-10-22-us6-full-month-retry.md
git commit -m "test(us6): failed monthly job does not seal the Hong Kong month"
```

---

## Spec coverage self-check

| Spec item | Task |
|-----------|------|
| T1 mid-fail → full list second run, no cursor keys | Task 1 |
| T2 failed job → `_already_succeeded_this_month` is False | Task 2 |
| No runner/CLI product changes unless tests fail | Both (stop rule) |

## Placeholder / consistency self-check

- Job type string `monthly_product_fields` matches US-5.
- `excerpt_month` ISO uses `YYYY-MM-DD` first-of-month as written by runner (`month.isoformat()`).
- No TBD.

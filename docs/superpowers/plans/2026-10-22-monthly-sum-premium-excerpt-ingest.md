# Monthly Sum / Premium / Excerpt Ingest (US-5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On each Hong Kong calendar month, automatically fetch China Life (Overseas) product pages and write `sum_assured`, `premium`, and `excerpt_date` into the product library without operator hand-tuning.

**Architecture:** One in-process monthly batch (no orchestration engine, no MCP). Pure extractors take HTML; the runner accepts an injectable `fetch(url) -> str` so tests never hit the network. Updates existing `products` rows matched by `official_url`. Records `product_sources` and a `data_update_jobs` row with `job_type="monthly_product_fields"`. Pages without a single sum/premium leave those fields empty and mark `no_single_number` in source JSON. One page request failure fails the job; already-written rows stay (idempotent overwrite on next full-month run). Hand-run seed scripts are not this path.

**Tech Stack:** FastAPI backend, SQLAlchemy models, Alembic, pytest, stdlib `urllib` for live fetch (same style as existing scripts).

**Spec:** `docs/superpowers/specs/2026-10-22-monthly-sum-premium-excerpt-ingest-design.md`

**Story:** US-5 in `docs/2026-10-22-用户故事-保额保费摘录日期.md`

---

## File map

| File | Responsibility |
|------|----------------|
| Create `backend/alembic/versions/phase8_001_product_sum_premium_excerpt.py` | Add `sum_assured`, `premium`, `excerpt_date` columns |
| Modify `backend/app/models.py` | ORM fields on `Product` |
| Modify `backend/app/schemas.py` | Expose the three fields on `ProductDetailOut` (read path for验收) |
| Create `backend/app/product_fields_extract.py` | URL allowlist, HK month, single-number extraction from HTML |
| Create `backend/app/monthly_product_fields.py` | Batch runner: list URLs, fetch, update DB, job row |
| Create `backend/app/jobs/__init__.py` | Package marker |
| Create `backend/app/jobs/monthly_product_fields_cli.py` | `python -m app.jobs.monthly_product_fields_cli` entry for scheduler |
| Create `backend/tests/test_product_fields_extract.py` | Unit tests for extract + allowlist + month |
| Create `backend/tests/test_monthly_product_fields.py` | Runner tests with fake fetch |
| Create `backend/tests/fixtures/product_pages/single_numbers.html` | Fixture with one sum + one premium |
| Create `backend/tests/fixtures/product_pages/no_single_number.html` | Fixture with ranges / multiple amounts |

Do **not** modify `scripts/discover_chinalife_product_urls.py` or `scripts/build_chinalife_product_seed.py` to “become” this path.

---

### Task 1: Schema — three nullable columns

**Files:**
- Create: `backend/alembic/versions/phase8_001_product_sum_premium_excerpt.py`
- Modify: `backend/app/models.py` (Product class ~148–165)
- Modify: `backend/app/schemas.py` (`ProductDetailOut`)
- Test: `backend/tests/test_monthly_product_fields.py` (started here; expanded in Task 4)

- [ ] **Step 1: Write failing test that Product accepts the three fields**

```python
# backend/tests/test_monthly_product_fields.py
from __future__ import annotations

from datetime import date

from app import db as db_mod
from app.models import Product


def test_product_model_has_sum_premium_excerpt_fields() -> None:
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        p = Product(
            id="prod-fields-smoke",
            name="smoke",
            category="医疗",
            sum_assured="HKD 1,000,000",
            premium="HKD 500",
            excerpt_date=date(2026, 10, 1),
        )
        s.add(p)
        s.commit()
        row = s.get(Product, "prod-fields-smoke")
        assert row is not None
        assert row.sum_assured == "HKD 1,000,000"
        assert row.premium == "HKD 500"
        assert row.excerpt_date == date(2026, 10, 1)
    finally:
        s.close()
```

- [ ] **Step 2: Run test — expect fail (columns missing)**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -m pytest tests/test_monthly_product_fields.py::test_product_model_has_sum_premium_excerpt_fields -v`

Expected: FAIL (AttributeError or sqlite operational error for unknown columns)

- [ ] **Step 3: Add Alembic migration**

```python
# backend/alembic/versions/phase8_001_product_sum_premium_excerpt.py
"""products: sum_assured, premium, excerpt_date"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "phase8_001"
down_revision = "phase7_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("sum_assured", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("premium", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("excerpt_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "excerpt_date")
    op.drop_column("products", "premium")
    op.drop_column("products", "sum_assured")
```

- [ ] **Step 4: Update ORM + schema**

On `Product` in `backend/app/models.py`, after `is_sample`:

```python
from datetime import date  # ensure imported at top if missing

sum_assured: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
premium: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
excerpt_date: Mapped[date | None] = mapped_column(nullable=True, default=None)
```

On `ProductDetailOut` in `backend/app/schemas.py`:

```python
sum_assured: str | None = None
premium: str | None = None
excerpt_date: str | None = None  # ISO date YYYY-MM-DD when present
```

Wire `knowledge` product detail response to pass these three fields when reading from DB (same router that builds `ProductDetailOut` today). If the mapper currently omits unknown fields, add the three assignments next to `official_url`.

- [ ] **Step 5: Apply migration in test env path**

Tests use `create_all` from metadata — after ORM update, `create_all` creates new columns on fresh sqlite. For existing developer DBs:

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && alembic upgrade head`

- [ ] **Step 6: Re-run test — expect pass**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -m pytest tests/test_monthly_product_fields.py::test_product_model_has_sum_premium_excerpt_fields -v`

Expected: PASS

- [ ] **Step 7: Commit** (only if the operator asked for a commit)

```bash
git add backend/alembic/versions/phase8_001_product_sum_premium_excerpt.py backend/app/models.py backend/app/schemas.py backend/app/routers/knowledge.py backend/tests/test_monthly_product_fields.py
git commit -m "feat(products): add sum_assured, premium, excerpt_date columns"
```

---

### Task 2: Extract helpers — allowlist, HK month, single numbers

**Files:**
- Create: `backend/app/product_fields_extract.py`
- Create: `backend/tests/test_product_fields_extract.py`
- Create: `backend/tests/fixtures/product_pages/single_numbers.html`
- Create: `backend/tests/fixtures/product_pages/no_single_number.html`

- [ ] **Step 1: Write fixtures**

`backend/tests/fixtures/product_pages/single_numbers.html`:

```html
<html><body>
<p>保险金额（保额）：HKD 1,000,000</p>
<p>保费：HKD 500</p>
</body></html>
```

`backend/tests/fixtures/product_pages/no_single_number.html`:

```html
<html><body>
<p>保额：HKD 500,000 至 HKD 2,000,000</p>
<p>保费视年龄而定，例如 HKD 200、HKD 350、HKD 500</p>
</body></html>
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_product_fields_extract.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.product_fields_extract import (
    allowed_product_url,
    excerpt_month_start,
    extract_sum_and_premium,
)

FIXTURES = Path(__file__).parent / "fixtures" / "product_pages"
HK = ZoneInfo("Asia/Hong_Kong")


def test_allowed_product_url_accepts_chinalife_product_page() -> None:
    assert allowed_product_url(
        "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/example-plan"
    )
    assert allowed_product_url(
        "https://chinalife.com.hk/zh-hk/products/insurance/savings/foo"
    )


def test_allowed_product_url_rejects_others() -> None:
    assert not allowed_product_url("https://www.example.com/products/insurance/x")
    assert not allowed_product_url("https://www.chinalife.com.hk/zh-hk/about")
    assert not allowed_product_url("https://www.chinalife.com.hk/zh-hk/products/insurance")


def test_excerpt_month_start_hong_kong() -> None:
    # 2026-10-31 23:30 UTC == 2026-11-01 07:30 HKT → November
    dt = datetime(2026, 10, 31, 23, 30, tzinfo=ZoneInfo("UTC"))
    assert excerpt_month_start(dt) == datetime(2026, 11, 1, tzinfo=HK).date()


def test_extract_single_numbers() -> None:
    html = (FIXTURES / "single_numbers.html").read_text(encoding="utf-8")
    result = extract_sum_and_premium(html)
    assert result.sum_assured == "HKD 1,000,000"
    assert result.premium == "HKD 500"
    assert result.no_single_number is False


def test_extract_no_single_number() -> None:
    html = (FIXTURES / "no_single_number.html").read_text(encoding="utf-8")
    result = extract_sum_and_premium(html)
    assert result.sum_assured is None
    assert result.premium is None
    assert result.no_single_number is True
```

- [ ] **Step 3: Run tests — expect fail**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -m pytest tests/test_product_fields_extract.py -v`

Expected: FAIL import / missing module

- [ ] **Step 4: Implement extractors**

```python
# backend/app/product_fields_extract.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

HK = ZoneInfo("Asia/Hong_Kong")

_AMOUNT = re.compile(
    r"(?:HKD|港元|港幣)\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractResult:
    sum_assured: str | None
    premium: str | None
    no_single_number: bool


def allowed_product_url(url: str) -> bool:
    p = urlparse((url or "").strip())
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "chinalife.com.hk":
        return False
    path = (p.path or "").rstrip("/")
    # must be under /products/insurance/<category>/<slug> (slug present)
    parts = [x for x in path.split("/") if x]
    # e.g. zh-hk products insurance medical example-plan
    try:
        i = parts.index("products")
    except ValueError:
        return False
    if i + 3 >= len(parts):
        return False
    if parts[i + 1] != "insurance":
        return False
    # category + slug required
    return bool(parts[i + 2]) and bool(parts[i + 3])


def excerpt_month_start(when: datetime) -> date:
    local = when.astimezone(HK)
    return date(local.year, local.month, 1)


def _label_amounts(html: str, labels: tuple[str, ...]) -> list[str]:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    found: list[str] = []
    for label in labels:
        for m in re.finditer(re.escape(label) + r".{0,40}?" + _AMOUNT.pattern, text, flags=re.I):
            am = _AMOUNT.search(m.group(0))
            if am:
                found.append(f"HKD {am.group(1)}")
    return found


def extract_sum_and_premium(html: str) -> ExtractResult:
    sums = _label_amounts(html, ("保险金额", "保險金額", "保额", "保額", "Sum Assured", "Sum insured"))
    premiums = _label_amounts(html, ("保费", "保費", "Premium"))
    # "单一数字": exactly one distinct amount for sum and one for premium
    sum_ok = len(set(sums)) == 1
    prem_ok = len(set(premiums)) == 1
    if sum_ok and prem_ok:
        return ExtractResult(sum_assured=sums[0], premium=premiums[0], no_single_number=False)
    # If either side is missing or multi-valued → leave both empty per design (no inventing)
    return ExtractResult(sum_assured=None, premium=None, no_single_number=True)
```

Note: if live pages use different label wording, extend the label tuples in a follow-up; do not invent amounts.

- [ ] **Step 5: Run tests — expect pass**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -m pytest tests/test_product_fields_extract.py -v`

Expected: PASS

- [ ] **Step 6: Commit** (only if operator asked)

```bash
git add backend/app/product_fields_extract.py backend/tests/test_product_fields_extract.py backend/tests/fixtures/product_pages
git commit -m "feat: extract single sum/premium and allowlist China Life URLs"
```

---

### Task 3: Monthly batch runner (injectable fetch)

**Files:**
- Create: `backend/app/monthly_product_fields.py`
- Modify: `backend/tests/test_monthly_product_fields.py`

- [ ] **Step 1: Write failing runner tests**

Append to `backend/tests/test_monthly_product_fields.py`:

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.models import DataUpdateJob, Product, ProductSource
from app.monthly_product_fields import run_monthly_product_fields

HK = ZoneInfo("Asia/Hong_Kong")
FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures" / "product_pages"


def _seed_product(url: str, pid: str = "prod-cl-1") -> None:
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        row = s.get(Product, pid)
        if row:
            s.delete(row)
            s.flush()
        s.add(
            Product(
                id=pid,
                name="测试产品",
                category="医疗",
                official_url=url,
                review_status="active",
            )
        )
        s.commit()
    finally:
        s.close()


def test_run_writes_fields_from_fetch() -> None:
    url = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/example-plan"
    _seed_product(url)
    html = (FIXTURES / "single_numbers.html").read_text(encoding="utf-8")

    def fetch(u: str) -> str:
        assert u == url
        return html

    when = datetime(2026, 10, 15, 12, 0, tzinfo=HK)
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=fetch,
            now=when,
        )
        s.commit()
        assert job.status == "success"
        row = s.get(Product, "prod-cl-1")
        assert row is not None
        assert row.sum_assured == "HKD 1,000,000"
        assert row.premium == "HKD 500"
        assert row.excerpt_date == date(2026, 10, 1)
        sources = s.query(ProductSource).filter_by(product_id="prod-cl-1").all()  # or select()
        assert any(x.kind == "monthly_auto" for x in sources)
        assert any(
            (x.raw_json or {}).get("no_single_number") is False for x in sources if x.kind == "monthly_auto"
        )
    finally:
        s.close()


def test_run_no_single_number_leaves_empty() -> None:
    url = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/range-plan"
    _seed_product(url, pid="prod-cl-2")
    html = (FIXTURES / "no_single_number.html").read_text(encoding="utf-8")

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=lambda u: html,
            now=datetime(2026, 10, 15, 12, 0, tzinfo=HK),
        )
        s.commit()
        assert job.status == "success"
        row = s.get(Product, "prod-cl-2")
        assert row is not None
        assert row.sum_assured is None
        assert row.premium is None
        assert row.excerpt_date == date(2026, 10, 1)
        src = s.query(ProductSource).filter_by(product_id="prod-cl-2", kind="monthly_auto").one()
        assert src.raw_json["no_single_number"] is True
    finally:
        s.close()


def test_run_rejects_non_chinalife_url() -> None:
    url = "https://www.example.com/products/insurance/medical/x"
    _seed_product(url, pid="prod-bad")
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=lambda u: "<html></html>",
            now=datetime(2026, 10, 15, 12, 0, tzinfo=HK),
        )
        s.commit()
        assert job.status == "success"
        row = s.get(Product, "prod-bad")
        assert row is not None
        assert row.sum_assured is None
        assert row.excerpt_date is None
    finally:
        s.close()


def test_run_fetch_failure_marks_job_failed() -> None:
    url = "https://www.chinalife.com.hk/zh-hk/products/insurance/medical/example-plan"
    _seed_product(url, pid="prod-cl-fail")

    def fetch(_u: str) -> str:
        raise TimeoutError("network down")

    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        job = run_monthly_product_fields(
            db=s,
            product_urls=[url],
            fetch=fetch,
            now=datetime(2026, 10, 15, 12, 0, tzinfo=HK),
        )
        s.commit()
        assert job.status == "failed"
        assert "network" in (job.error_message or "").lower() or "Timeout" in job.error_message
    finally:
        s.close()
```

Prefer SQLAlchemy 2.0 `select` if the codebase avoids `session.query` — match `test_phase3_real_data.py` style.

- [ ] **Step 2: Run tests — expect fail**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -m pytest tests/test_monthly_product_fields.py -v`

Expected: FAIL missing `run_monthly_product_fields`

- [ ] **Step 3: Implement runner**

```python
# backend/app/monthly_product_fields.py
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataUpdateJob, Product, ProductSource
from app.product_fields_extract import (
    allowed_product_url,
    excerpt_month_start,
    extract_sum_and_premium,
)

FetchFn = Callable[[str], str]
JOB_TYPE = "monthly_product_fields"


def run_monthly_product_fields(
    *,
    db: Session,
    product_urls: Sequence[str],
    fetch: FetchFn,
    now: datetime,
) -> DataUpdateJob:
    job = DataUpdateJob(job_type=JOB_TYPE, status="pending")
    db.add(job)
    db.flush()
    month = excerpt_month_start(now)
    updated = 0
    skipped = 0
    no_single = 0
    try:
        for url in product_urls:
            if not allowed_product_url(url):
                skipped += 1
                continue
            html = fetch(url)
            extracted = extract_sum_and_premium(html)
            product = db.scalar(select(Product).where(Product.official_url == url))
            if product is None:
                skipped += 1
                continue
            product.sum_assured = extracted.sum_assured
            product.premium = extracted.premium
            product.excerpt_date = month
            raw: dict[str, Any] = {
                "no_single_number": extracted.no_single_number,
                "excerpt_month": month.isoformat(),
                "source_url": url,
            }
            if extracted.no_single_number:
                no_single += 1
            db.add(
                ProductSource(
                    product_id=product.id,
                    kind="monthly_auto",
                    ref=url,
                    raw_json=raw,
                )
            )
            updated += 1
        job.status = "success"
        job.finished_at = datetime.utcnow()
        job.detail_json = {
            "updated_count": updated,
            "skipped_count": skipped,
            "no_single_number_count": no_single,
            "excerpt_month": month.isoformat(),
        }
    except Exception as exc:
        job.status = "failed"
        job.finished_at = datetime.utcnow()
        job.error_message = str(exc)
        job.detail_json = {
            "updated_count": updated,
            "skipped_count": skipped,
            "no_single_number_count": no_single,
            "excerpt_month": month.isoformat(),
        }
    return job
```

- [ ] **Step 4: Run tests — expect pass**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -m pytest tests/test_monthly_product_fields.py tests/test_product_fields_extract.py -v`

Expected: PASS

- [ ] **Step 5: Commit** (only if operator asked)

```bash
git add backend/app/monthly_product_fields.py backend/tests/test_monthly_product_fields.py
git commit -m "feat: monthly product fields batch runner with injectable fetch"
```

---

### Task 4: CLI entry for scheduler (full auto, not hand seed scripts)

**Files:**
- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/monthly_product_fields_cli.py`

- [ ] **Step 1: Implement URL listing from DB (no hand seed script)**

Inside `monthly_product_fields_cli.py`, list URLs from existing active products whose `official_url` passes `allowed_product_url`. Do not call `scripts/build_chinalife_product_seed.py`.

```python
# backend/app/jobs/monthly_product_fields_cli.py
"""Scheduler entry: python -m app.jobs.monthly_product_fields_cli

Idempotent for the calendar month: if a successful monthly_product_fields job
already exists for the current Hong Kong month, exit 0 without re-fetching.
"""

from __future__ import annotations

import ssl
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import db as db_mod
from app.models import DataUpdateJob, Product
from app.monthly_product_fields import JOB_TYPE, run_monthly_product_fields
from app.product_fields_extract import allowed_product_url, excerpt_month_start

HK = ZoneInfo("Asia/Hong_Kong")
UA = "Mozilla/5.0 (compatible; hkia-assistant-monthly-fields/1.0)"


def _http_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def _already_succeeded_this_month(db, month_iso: str) -> bool:
    rows = db.scalars(
        select(DataUpdateJob)
        .where(DataUpdateJob.job_type == JOB_TYPE, DataUpdateJob.status == "success")
        .order_by(DataUpdateJob.id.desc())
        .limit(20)
    ).all()
    for j in rows:
        detail = j.detail_json or {}
        if detail.get("excerpt_month") == month_iso:
            return True
    return False


def main() -> int:
    if db_mod.SessionLocal is None:
        db_mod.init_engine()
        db_mod.create_tables()
    now = datetime.now(tz=HK)
    month = excerpt_month_start(now)
    s = db_mod.SessionLocal()  # type: ignore[misc]
    try:
        if _already_succeeded_this_month(s, month.isoformat()):
            print(f"skip: already succeeded for {month.isoformat()}")
            return 0
        urls = [
            r.official_url
            for r in s.scalars(select(Product).where(Product.review_status == "active")).all()
            if allowed_product_url(r.official_url or "")
        ]
        job = run_monthly_product_fields(db=s, product_urls=urls, fetch=_http_fetch, now=now)
        s.commit()
        print(f"job_id={job.id} status={job.status} detail={job.detail_json}")
        return 0 if job.status == "success" else 1
    finally:
        s.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-run module import**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -c "from app.jobs.monthly_product_fields_cli import main; print('ok')"`

Expected: prints `ok`

- [ ] **Step 3: Document scheduler one-liner in plan completion note (no README rewrite unless asked)**

Operator schedule (example, Windows Task Scheduler or cron):

```text
cd C:\Users\Eason Zhao\Desktop\hkia-assistant\backend && python -m app.jobs.monthly_product_fields_cli
```

Run at least monthly; safe to run more often (idempotent skip after success for that HK month).

- [ ] **Step 4: Commit** (only if operator asked)

```bash
git add backend/app/jobs/__init__.py backend/app/jobs/monthly_product_fields_cli.py
git commit -m "feat: CLI entry for monthly product fields auto-ingest"
```

---

### Task 5: Regression — seed scripts are not the pass path

**Files:**
- Modify: `backend/tests/test_monthly_product_fields.py` only

- [ ] **Step 1: Add assertion test documenting non-path**

```python
def test_hand_seed_scripts_are_not_monthly_job_type() -> None:
    """US-5 pass requires job_type monthly_product_fields, not seed imports."""
    from app.monthly_product_fields import JOB_TYPE

    assert JOB_TYPE == "monthly_product_fields"
    assert JOB_TYPE != "manual"
```

- [ ] **Step 2: Run full related suite**

Run: `cd "C:\Users\Eason Zhao\Desktop\hkia-assistant\backend" && python -m pytest tests/test_product_fields_extract.py tests/test_monthly_product_fields.py -v`

Expected: PASS

- [ ] **Step 3: Commit** (only if operator asked)

```bash
git add backend/tests/test_monthly_product_fields.py
git commit -m "test: assert monthly job type is not hand-seed path"
```

---

## Spec coverage self-check

| Spec requirement | Task |
|------------------|------|
| Columns `sum_assured`, `premium`, `excerpt_date` | Task 1 |
| Only China Life Overseas product pages | Task 2 allowlist + Task 3 skip |
| No single number → empty + mark | Task 2 extract + Task 3 |
| Excerpt month = HK calendar month of run | Task 2 + Task 3 |
| Own loop / injectable fetch / no engine | Task 3–4 |
| Job row; no resume cursor | Task 3 |
| Page fetch failure → job failed | Task 3 |
| Full auto CLI, not hand seed scripts | Task 4–5 |
| US-1–4, US-6–7 out of scope | Not in this plan |

## Placeholder / consistency self-check

- Field names fixed: `sum_assured`, `premium`, `excerpt_date`
- Job type fixed: `monthly_product_fields`
- Source kind fixed: `monthly_auto`
- No TBD / “add error handling later”
- Live label wording may miss some pages → empty + `no_single_number` (allowed); do not invent amounts

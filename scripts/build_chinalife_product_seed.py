"""Build phase3 JSON seed from China Life (Overseas) HK public product pages (listing + per-page title)."""

from __future__ import annotations

import html
import json
import re
import ssl
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://www.chinalife.com.hk"

CATEGORY_PAGES: list[tuple[str, str]] = [
    ("savings", f"{BASE}/zh-hk/products/insurance/savings"),
    ("medical", f"{BASE}/zh-hk/products/insurance/medical"),
    ("critical-illness", f"{BASE}/zh-hk/products/insurance/critical-illness"),
    ("life-protection", f"{BASE}/zh-hk/products/insurance/life-protection"),
    ("retirement", f"{BASE}/zh-hk/products/insurance/retirement"),
    ("accident", f"{BASE}/zh-hk/products/insurance/accident"),
    ("juvenile-protection", f"{BASE}/zh-hk/products/insurance/juvenile-protection"),
]

CATEGORY_LABEL: dict[str, str] = {
    "savings": "储蓄",
    "medical": "医疗",
    "critical-illness": "重疾",
    "life-protection": "人寿",
    "retirement": "年金/退休",
    "accident": "意外",
    "juvenile-protection": "少儿保障",
}

SLUG_BLACKLIST = {
    "insurance",
    "savings",
    "medical",
    "critical-illness",
    "life-protection",
    "retirement",
    "accident",
    "juvenile-protection",
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Listing cards有时候会把延期年金归在「储蓄」等栏目，这里按产品性质手工纠偏。
CATEGORY_OVERRIDE_BY_SLUG_LOWER: dict[str, str] = {
    "comfort-life-deferred-annuity-plan": "retirement",
    "graceful-life-deferred-annuity-plan-ii": "retirement",
    "noble-legend-life-insurance-plan": "life-protection",
    "promise-family-protector": "juvenile-protection",
    "totalprotect-refundable-accident-disability-protection-plan": "accident",
}


class _ALinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        d = dict(attrs)
        h = d.get("href")
        if h:
            self.links.append(h)


class _MetaOg(HTMLParser):
    """Capture og:title / og:description / <title> (first wins for each)."""

    def __init__(self) -> None:
        super().__init__()
        self.og_title: str | None = None
        self.og_description: str | None = None
        self.doc_title: str | None = None
        self._in_title = False
        self._title_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k.lower(): v for k, v in attrs}
        if tag == "meta":
            prop = (d.get("property") or d.get("name") or "").lower()
            content = (d.get("content") or "").strip()
            if prop == "og:title" and content and self.og_title is None:
                self.og_title = content
            if prop == "og:description" and content and self.og_description is None:
                self.og_description = content
        if tag == "title":
            self._in_title = True
            self._title_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._in_title:
            self._in_title = False
            if self.doc_title is None:
                self.doc_title = "".join(self._title_buf).strip()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buf.append(data)


def _normalize_href(href: str) -> str | None:
    if href.startswith("/"):
        return (BASE + href).split("#")[0].rstrip("/")
    if href.startswith("http"):
        return href.split("#")[0].rstrip("/")
    return None


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


# Keep stable IDs aligned with legacy seeds (import upserts by id).
CANONICAL_ID_BY_SLUG_LOWER: dict[str, str] = {
    "great-harvest-income-plan": "clo-great-harvest-income-plan",
    "evertogether-savings-insurance-plan-supreme": "clo-evertogether-supreme",
    "elite-care-critical-illness-insurance-plan": "clo-elite-care-critical-illness",
    "enjoyable-life-income-plan": "clo-enjoyable-life-income-plan",
    "mastercare-medical-plan": "clo-mastercare-medical-plan",
    "protector-critical-illness-insurance-plan": "clo-protector-critical-illness-plan",
    "joyful-care-critical-illness-insurance-plan": "clo-joyful-care-critical-illness-plan",
    "noble-legend-life-insurance-plan": "clo-noble-legend-life-insurance-plan",
    "wise-legend-multi-currency-plan": "clo-wise-legend-multi-currency-plan",
    "graceful-life-deferred-annuity-plan-ii": "clo-graceful-life-deferred-annuity-plan-ii",
}


def _make_id(slug: str) -> str:
    key = slug.strip().lower().replace("_", "-")
    if key in CANONICAL_ID_BY_SLUG_LOWER:
        return CANONICAL_ID_BY_SLUG_LOWER[key]
    return f"clo-{key}"


def _clean_title(raw: str) -> str:
    t = raw.strip()
    for sep in (" | 中國人壽(海外)", " | China Life (Overseas)", " | 中国人寿（海外）", " | China Life"):
        if sep in t:
            t = t.split(sep, 1)[0].strip()
    return t


def _fetch(url: str, referer: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": referer, "Accept-Language": "zh-HK,zh-TW,zh-CN,en;q=0.9"},
    )
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, context=ctx, timeout=35).read().decode("utf-8", "replace")


def _extract_meta_desc(raw_html: str) -> str:
    patterns = (
        r'property=["\']og:description["\']\s+content=["\']([^"\']*)["\']',
        r'content=["\']([^"\']*)["\']\s+property=["\']og:description["\']',
        r'name=["\']description["\']\s+content=["\']([^"\']*)["\']',
        r'content=["\']([^"\']*)["\']\s+name=["\']description["\']',
    )
    for pat in patterns:
        m = re.search(pat, raw_html, re.I | re.DOTALL)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def _discover() -> dict[str, str]:
    """product_url -> category_key (first listing wins)."""
    prod_pat = re.compile(r"/zh-hk/products/insurance/([^?#\"]+)$")
    out: dict[str, str] = {}
    for cat_key, cat_url in CATEGORY_PAGES:
        page_html = _fetch(cat_url, cat_url)
        parser = _ALinks()
        parser.feed(page_html)
        for h in parser.links:
            u = _normalize_href(h)
            if not u or "chinalife.com.hk" not in u:
                continue
            if "/zh-hk/products/insurance/" not in u:
                continue
            m = prod_pat.search(u.rstrip("/"))
            if not m:
                continue
            slug = m.group(1).rstrip("/").split("/")[-1]
            if slug.lower() in {x.lower() for x in SLUG_BLACKLIST}:
                continue
            if u not in out:
                out[u] = cat_key
    return out


def _page_meta(product_url: str, category_url: str) -> tuple[str, str]:
    raw = _fetch(product_url, category_url)
    p = _MetaOg()
    p.feed(raw)
    name = _clean_title(p.og_title or p.doc_title or _slug_from_url(product_url))
    desc = (p.og_description or "").strip() or _extract_meta_desc(raw)
    desc = " ".join(desc.split())
    if len(desc) > 800:
        desc = desc[:800] + "…"
    return name, desc


def _row_for_url(product_url: str, category_key: str) -> dict[str, object]:
    slug = _slug_from_url(product_url)
    slug_l = slug.strip().lower().replace("_", "-")
    category_key = CATEGORY_OVERRIDE_BY_SLUG_LOWER.get(slug_l, category_key)
    cat_url = dict(CATEGORY_PAGES).get(category_key, f"{BASE}/zh-hk/products/insurance")
    name, og_desc = _page_meta(product_url, cat_url)
    label = CATEGORY_LABEL.get(category_key, "保障")
    summary_core = og_desc or f"本产品资料摘录自中国人寿（海外）官方网站产品页，类型：{label}。"
    highlights = (
        (og_desc[:220] + ("…" if len(og_desc) > 220 else ""))
        if og_desc
        else f"官方网站产品页公开的概要信息（{label}）；具体保障与条款以正式保单文件为准。"
    )
    return {
        "id": _make_id(slug),
        "name": name,
        "category": label,
        "highlights": highlights,
        "coverage_summary": f"保障与权益以官网及保单条款为准。【摘录】{summary_core}",
        "target_audience": f"关注{label}规划的客户；是否适合需结合个人需求与财务状况评估。",
        "clause_summary": "上述字段为网站公开信息摘录，不构成要约。等待期、除外责任、不保事项、定义与理赔条件等，以保险公司正式条款及最新披露为准。",
        "official_url": product_url,
        "source_note": "China Life (Overseas) 官网产品页自动摘录（见 official_url），管理员可后续人工核稿。",
        "review_status": "pending_review",
        "is_sample": False,
    }


def main() -> None:
    out_path = Path(__file__).resolve().parents[1] / "backend" / "app" / "data" / "phase3_products_seed.v3.json"
    mapping = _discover()
    rows: list[dict[str, object]] = []
    for url in sorted(mapping.keys()):
        try:
            rows.append(_row_for_url(url, mapping[url]))
        except Exception as exc:
            print(f"SKIP {url} ({exc})", file=sys.stderr)
    rows.sort(key=lambda r: str(r.get("id", "")))
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} products to {out_path}")


if __name__ == "__main__":
    main()

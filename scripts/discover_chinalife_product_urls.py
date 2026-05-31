"""Discover individual product page URLs from China Life (Overseas) HK category listing pages."""

from __future__ import annotations

import re
import ssl
import sys
import urllib.request
from html.parser import HTMLParser

BASE = "https://www.chinalife.com.hk"

CATEGORIES = [
    f"{BASE}/zh-hk/products/insurance/savings",
    f"{BASE}/zh-hk/products/insurance/medical",
    f"{BASE}/zh-hk/products/insurance/critical-illness",
    f"{BASE}/zh-hk/products/insurance/life-protection",
    f"{BASE}/zh-hk/products/insurance/retirement",
    f"{BASE}/zh-hk/products/insurance/accident",
    f"{BASE}/zh-hk/products/insurance/juvenile-protection",
]

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


def _normalize(href: str) -> str | None:
    if href.startswith("/"):
        return (BASE + href).split("#")[0].rstrip("/")
    if href.startswith("http"):
        return href.split("#")[0].rstrip("/")
    return None


def main() -> None:
    ctx = ssl.create_default_context()
    seen: set[str] = set()
    prod_pat = re.compile(r"/products/insurance/([^?#\"]+)$")

    for cat in CATEGORIES:
        req = urllib.request.Request(cat, headers={"User-Agent": "Mozilla/5.0"})
        try:
            html = (
                urllib.request.urlopen(req, context=ctx, timeout=30)
                .read()
                .decode("utf-8", "replace")
            )
        except Exception as exc:
            print(f"WARN {cat} {exc}", file=sys.stderr)
            continue
        parser = _ALinks()
        parser.feed(html)
        for h in parser.links:
            u = _normalize(h)
            if not u or "chinalife.com.hk" not in u:
                continue
            if "/products/insurance/" not in u:
                continue
            m = prod_pat.search(u.rstrip("/"))
            if not m:
                continue
            slug = m.group(1).rstrip("/").split("/")[-1]
            if slug in SLUG_BLACKLIST:
                continue
            seen.add(u)

        print(f"{cat} -> accumulated {len(seen)}", file=sys.stderr)

    for u in sorted(seen):
        print(u)


if __name__ == "__main__":
    main()

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


def _window_after_label(text: str, end: int, *, limit: int = 50) -> str:
    chunk = text[end : end + limit]
    for stop in (" 保费", " 保費", " Premium", " 保险金额", " 保險金額", " 保额", " 保額"):
        i = chunk.find(stop)
        if i != -1:
            chunk = chunk[:i]
    return chunk


def _is_letter_or_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        ("a" <= ch <= "z")
        or ("A" <= ch <= "Z")
        or (0x4E00 <= code <= 0x9FFF)
    )


def _label_amounts(html: str, labels: tuple[str, ...]) -> list[str]:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    found: list[str] = []
    for label in labels:
        for m in re.finditer(re.escape(label), text, flags=re.I):
            start = m.start()
            if start > 0 and _is_letter_or_cjk(text[start - 1]):
                continue
            window = _window_after_label(text, m.end())
            amounts = [f"HKD {am.group(1)}" for am in _AMOUNT.finditer(window)]
            if len(amounts) == 1:
                found.append(amounts[0])
            elif len(amounts) > 1:
                found.extend(amounts)
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

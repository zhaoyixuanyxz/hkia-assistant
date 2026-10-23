from __future__ import annotations

from typing import Any

from app.schemas import ReportPayload, ReportProductPick

_DEFAULT_HYDRATED_RATIONALE = (
    "本条为系统在可检索产品候选中择取，便于与您在持牌顾问处核对；"
    "责任范围、费率与承保条件以官方条款及顾问说明为准。"
)


def _opt_str(cand: dict, key: str, fallback: str | None) -> str | None:
    if key not in cand:
        return fallback
    v = cand.get(key)
    if v is None:
        return None
    return str(v)


def hydrate_concrete_picks_from_candidates(
    payload: ReportPayload,
    candidates: list[dict[str, Any]],
    *,
    max_picks: int = 3,
) -> ReportPayload:
    """When the model omits picks or they were all stripped, surface top retrieval hits.

    Keeps IDs within the same grounded candidate list; does not invent products.
    """
    if payload.concrete_product_picks:
        return payload
    if not candidates:
        return payload

    candidate_map: dict[str, dict] = {}
    for c in candidates:
        pid = c.get("product_id")
        if pid:
            candidate_map[str(pid)] = c

    picks: list[ReportProductPick] = []
    seen: set[str] = set()
    for c in candidates:
        pid = str(c.get("product_id") or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        reason = str(c.get("match_reason") or "").strip() or _DEFAULT_HYDRATED_RATIONALE
        picks.append(
            ReportProductPick(
                product_id=pid,
                name=str(c.get("name") or ""),
                rationale=reason,
                source_url=str(c.get("source_url") or ""),
                sum_assured=_opt_str(c, "sum_assured", None),
                premium=_opt_str(c, "premium", None),
                excerpt_date=_opt_str(c, "excerpt_date", None),
            )
        )
        if len(picks) >= max_picks:
            break

    if not picks:
        return payload

    out = payload.model_copy(update={"concrete_product_picks": picks})
    return enrich_product_picks_with_sources(out, candidate_map)


def _present(value: str | None) -> bool:
    return value is not None and str(value).strip() != ""


def filter_picks_requiring_three_fields(payload: ReportPayload) -> ReportPayload:
    kept = [
        p
        for p in payload.concrete_product_picks
        if _present(p.sum_assured) and _present(p.premium) and _present(p.excerpt_date)
    ]
    return payload.model_copy(update={"concrete_product_picks": kept})


def sanitize_concrete_product_picks(
    payload: ReportPayload, allowed_ids: set[str]
) -> ReportPayload:
    picks_list = [
        p
        for p in payload.concrete_product_picks
        if p.product_id and p.product_id in allowed_ids
    ]
    return payload.model_copy(update={"concrete_product_picks": picks_list})


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
                sum_assured=_opt_str(cand, "sum_assured", p.sum_assured),
                premium=_opt_str(cand, "premium", p.premium),
                excerpt_date=_opt_str(cand, "excerpt_date", p.excerpt_date),
            )
        )
    return payload.model_copy(update={"concrete_product_picks": picks})

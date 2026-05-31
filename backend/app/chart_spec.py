"""Report chart type registry and sanitization (phase 4)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Exported for API/schema + prompts alignment (JSON/token size vs UX richness).
GLOBAL_MAX_REPORT_CHARTS: int = 20


@dataclass(frozen=True)
class ChartBudget:
    """Dynamic chart cardinality & diversity hints from survey + structured profile."""

    max_charts: int
    min_distinct_types: int
    target_min_count: int


def count_structured_insight_signals(structured: dict[str, Any] | None) -> int:
    """Rough signal count so chart budget scales with conversational + merged JSON richness."""
    if not structured or not isinstance(structured, dict):
        return 0
    n = 0
    dims = structured.get("dimensions")
    if isinstance(dims, dict):
        for _k, raw in dims.items():
            if not isinstance(raw, str):
                continue
            v = raw.strip()
            if len(v) > 40:
                n += 3
            elif len(v) > 12:
                n += 2
            elif v:
                n += 1

    cats = structured.get("product_focus_categories")
    if isinstance(cats, list):
        n += sum(1 for c in cats if str(c).strip())

    kms = structured.get("key_memories")
    if isinstance(kms, list):
        n += min(len([x for x in kms if str(x).strip()]), 6)

    bh = structured.get("budget_hint")
    if isinstance(bh, str) and len(bh.strip()) > 8:
        n += 2

    return min(int(n), 48)


def compute_chart_budget(
    report_depth: str,
    *,
    optional_filled: int = 0,
    structured: dict[str, Any] | None = None,
) -> ChartBudget:
    """More survey + richer structured fuse → larger max chart count & diversity floor."""
    sig = int(optional_filled) + count_structured_insight_signals(structured)

    if report_depth == "deep":
        base_max, base_distinct, depth_target = 9, 4, 6
    elif report_depth == "enhanced":
        base_max, base_distinct, depth_target = 6, 3, 4
    else:
        base_max, base_distinct, depth_target = 4, 2, 3

    bonus = sig // 2 + sig // 5
    max_charts = min(GLOBAL_MAX_REPORT_CHARTS, base_max + bonus // 3 + sig // 4)
    max_charts = max(3, max_charts)

    min_distinct = base_distinct + sig // 5
    cap_by_space = min(max_charts, len(ALLOWED_CHART_TYPES))
    min_distinct = max(2, min(min_distinct, cap_by_space))

    target_min = depth_target + sig // 3
    target_min = min(max_charts, max(target_min, min_distinct))

    return ChartBudget(
        max_charts=max_charts,
        min_distinct_types=min_distinct,
        target_min_count=target_min,
    )

# Twelve Recharts-fronted kinds; composite uses optional "value2" for second series.
ALLOWED_CHART_TYPES: frozenset[str] = frozenset(
    {
        "radar",
        "pie",
        "donut",
        "line",
        "area",
        "bar",
        "bar_horizontal",
        "scatter",
        "radial_bar",
        "funnel",
        "composed",
        "treemap",
    }
)


def _normalize_point(row: dict[str, Any]) -> dict[str, Any]:
    """Keep name + numeric value/value2 for downstream rendering."""
    if not isinstance(row, dict):
        return {"name": "—", "value": 0.0}
    name = row.get("name")
    if name is None or name == "":
        name = "—"
    else:
        name = str(name)[:180]
    raw_v = row.get("value")
    try:
        value = float(raw_v)
    except (TypeError, ValueError):
        value = 0.0
    out: dict[str, Any] = {"name": name, "value": value}
    if "value2" in row:
        try:
            out["value2"] = float(row["value2"])
        except (TypeError, ValueError):
            pass
    return out


def sanitize_chart_item(raw: dict[str, Any] | Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    ctype = raw.get("type")
    if not isinstance(ctype, str):
        logger.warning("chart_drop_invalid_type type=%r", type(ctype).__name__)
        return None
    ctype = ctype.strip().lower().replace("-", "_")
    if ctype not in ALLOWED_CHART_TYPES:
        logger.warning("chart_drop_unknown_type type=%r", ctype)
        return None
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "图表"
    else:
        title = title.strip()[:200]
    data_raw = raw.get("data")
    if not isinstance(data_raw, list):
        data_raw = []
    data = [_normalize_point(r) for r in data_raw if r is not None]
    if len(data) < 1:
        logger.warning("chart_drop_empty_data type=%s", ctype)
        return None
    return {"type": ctype, "title": title, "data": data}


def sanitize_charts_list(raw: list[Any] | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        clean = sanitize_chart_item(item)
        if clean is not None:
            out.append(clean)
    return out


_CHART_FILLERS: list[tuple[str, str, list[dict[str, Any]]]] = [
    (
        "radar",
        "保障维度平衡（示意）",
        [
            {"name": "医疗", "value": 55},
            {"name": "人寿", "value": 50},
            {"name": "重疾", "value": 62},
            {"name": "意外", "value": 40},
        ],
    ),
    (
        "pie",
        "保障与储蓄结构（示意）",
        [
            {"name": "保障类", "value": 58},
            {"name": "储蓄类", "value": 28},
            {"name": "现金预留", "value": 14},
        ],
    ),
    (
        "donut",
        "风险偏好与币种倾向（示意）",
        [{"name": "稳健", "value": 62}, {"name": "进取", "value": 38}],
    ),
    (
        "bar_horizontal",
        "责任优先级对比（示意）",
        [{"name": "家庭支柱身故", "value": 74}, {"name": "治疗费用", "value": 71}, {"name": "退休金积累", "value": 53}],
    ),
    (
        "treemap",
        "保障责任块体量（示意）",
        [{"name": "重疾", "value": 220}, {"name": "医疗", "value": 185}, {"name": "寿险", "value": 260}],
    ),
    (
        "funnel",
        "配置推进阶段（示意）",
        [
            {"name": "厘清责任", "value": 100},
            {"name": "产品比对", "value": 74},
            {"name": "核保承保", "value": 38},
            {"name": "持续检视", "value": 22},
        ],
    ),
    (
        "scatter",
        "预算—保障密度（示意）",
        [{"name": "医疗", "value": 61}, {"name": "人寿", "value": 73}, {"name": "储蓄", "value": 54}],
    ),
    (
        "composed",
        "保障 vs 储蓄双序列（示意）",
        [{"name": "首期", "value": 62, "value2": 40}, {"name": "中段", "value": 71, "value2": 55}],
    ),
    (
        "area",
        "现金流关注走势（示意）",
        [{"name": "Year1", "value": 40}, {"name": "Year3", "value": 53}, {"name": "Year5", "value": 68}],
    ),
    (
        "line",
        "计划周期关注点（示意）",
        [{"name": "T1", "value": 42}, {"name": "T2", "value": 55}, {"name": "T3", "value": 63}],
    ),
    (
        "radial_bar",
        "单指标完成度刻度（示意）",
        [{"name": "保额充足度", "value": 66}, {"name": "分散度", "value": 48}],
    ),
    (
        "bar",
        "险种关注优先级（示意）",
        [
            {"name": "重疾", "value": 72},
            {"name": "医疗", "value": 68},
            {"name": "人寿", "value": 54},
        ],
    ),
]


def enforce_report_chart_depth(
    charts: list[dict[str, Any]],
    depth: str,
    *,
    budget: ChartBudget | None = None,
) -> list[dict[str, Any]]:
    """Honor model charts; pad with sanitized fillers until budget / diversity hints met."""
    budget = budget or compute_chart_budget(depth, optional_filled=0, structured=None)
    max_n = budget.max_charts
    req_distinct = min(
        budget.min_distinct_types,
        len(ALLOWED_CHART_TYPES),
        max_n,
    )
    target_floor = max(1, min(budget.target_min_count, max_n))
    need_cap = min(req_distinct, max_n, len(ALLOWED_CHART_TYPES))

    out: list[dict[str, Any]] = []
    for c in charts:
        if len(out) >= max_n:
            break
        if isinstance(c, dict):
            clean = sanitize_chart_item(c)
            if clean:
                out.append(clean)

    def type_set() -> set[str]:
        return {str(c.get("type")) for c in out if c.get("type")}

    def satisfied() -> bool:
        n = len(out)
        if n < target_floor:
            return False
        need_d = min(need_cap, n)
        return len(type_set()) >= need_d

    pad_i = 0
    while not satisfied() and len(out) < max_n:
        ctype, title, data = _CHART_FILLERS[pad_i % len(_CHART_FILLERS)]
        pad_i += 1
        t2 = title if ctype not in type_set() else f"{title}（视角 {pad_i}）"
        filler = sanitize_chart_item({"type": ctype, "title": t2, "data": data})
        if filler:
            out.append(filler)

    return out[:max_n]

"""Product IDs permanently removed from catalog (API + future imports)."""

from __future__ import annotations

# Retired per product decision — kept server-side so DB/Qdrant lag cannot surface them.
RETIRED_PRODUCT_IDS: frozenset[str] = frozenset(
    {
        "clo-enjoyable-life-income-plan",
    }
)


def is_retired_product_id(product_id: str) -> bool:
    return product_id in RETIRED_PRODUCT_IDS

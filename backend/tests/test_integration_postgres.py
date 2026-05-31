from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("HKIA_POSTGRES_URL"),
    reason="Set HKIA_POSTGRES_URL for Postgres integration checks",
)
def test_postgres_placeholder() -> None:
    """Placeholder for future connectivity/migration smoke tests."""
    assert os.getenv("HKIA_POSTGRES_URL", "").startswith("postgresql")

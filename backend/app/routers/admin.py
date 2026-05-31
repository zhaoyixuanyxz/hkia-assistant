from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user_optional
from app.models import Product, User

router = APIRouter(prefix="/admin", tags=["admin"])


class ProductPatchIn(BaseModel):
    review_status: str | None = None
    highlights: str | None = None
    coverage_summary: str | None = None
    clause_summary: str | None = None
    source_note: str | None = None


def _authorized_admin(x_admin_key: str | None, user: User | None) -> bool:
    expected = (get_settings().admin_api_key or "").strip()
    if expected and (x_admin_key or "").strip() == expected:
        return True
    return user is not None and getattr(user, "role", "user") == "admin"


@router.patch("/products/{product_id}")
def patch_product(
    product_id: str,
    body: ProductPatchIn,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> dict[str, Any]:
    if not _authorized_admin(x_admin_key, user):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )
    row = db.get(Product, product_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")
    if body.review_status is not None:
        if body.review_status not in {"active", "pending_review", "obsolete"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid review_status")
        row.review_status = body.review_status
    if body.highlights is not None:
        row.highlights = body.highlights.strip()
    if body.coverage_summary is not None:
        row.coverage_summary = body.coverage_summary.strip()
    if body.clause_summary is not None:
        row.clause_summary = body.clause_summary.strip()
    if body.source_note is not None:
        row.source_note = body.source_note.strip()
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "product_id": row.id, "review_status": row.review_status}

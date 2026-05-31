from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.embeddings import cosine_similarity, get_embedding_service
from app.models import Product
from app.product_data import load_retrievable_product_rows, product_to_row
from app.qdrant_store import qdrant_enabled, search_products as qdrant_search_products

from app.retired_products import RETIRED_PRODUCT_IDS, is_retired_product_id
from app.schemas import ProductDetailOut, ProductStubOut
from app.stub_data import filter_products, load_product_stubs

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/products", response_model=list[ProductStubOut])
def search_products(
    q: str | None = Query(None),
    category: str | None = Query(None),
    mode: str = Query("keyword", pattern="^(keyword|semantic|auto)$"),
    db: Session = Depends(get_db),
) -> list[ProductStubOut]:
    query_text = (q or "").strip()
    if mode == "auto":
        mode = "semantic" if query_text else "keyword"

    if mode == "semantic":
        rows = _semantic_rows(query_text, category)
    else:
        rows = _keyword_rows(db, query_text, category)
    rows = [r for r in rows if str(r.get("id", "")) not in RETIRED_PRODUCT_IDS]
    return [ProductStubOut.model_validate(r) for r in rows]


def _product_to_detail(row: Product) -> ProductDetailOut:
    return ProductDetailOut(
        id=row.id,
        name=row.name,
        category=row.category,
        highlights=row.highlights or "",
        coverage_summary=row.coverage_summary or "",
        target_audience=row.target_audience or "",
        clause_summary=row.clause_summary or "",
        source_note=row.source_note or "",
        official_url=row.official_url or "",
        is_sample=bool(row.is_sample),
        updated_at=row.updated_at.isoformat() + "Z",
        review_status=row.review_status,
    )


@router.get("/products/{product_id}", response_model=ProductDetailOut)
def get_product(product_id: str, db: Session = Depends(get_db)) -> ProductDetailOut:
    if is_retired_product_id(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    row = db.get(Product, product_id)
    if row is not None and row.review_status == "active":
        return _product_to_detail(row)

    for stub in load_product_stubs():
        if str(stub.get("id", "")) == product_id:
            raw_u = str(stub.get("updated_at", "")).strip()
            updated = raw_u if "T" in raw_u else f"{raw_u}T00:00:00Z" if raw_u else ""
            return ProductDetailOut(
                id=str(stub["id"]),
                name=str(stub.get("name", "")),
                category=str(stub.get("category", "")),
                highlights=str(stub.get("summary", "")),
                coverage_summary="",
                target_audience="",
                clause_summary="",
                source_note="Demo stub (not a real product).",
                official_url=str(stub.get("source_url", "")),
                is_sample=True,
                updated_at=updated or "1970-01-01T00:00:00Z",
                review_status="active",
            )

    raise HTTPException(status_code=404, detail="Product not found")


def _keyword_rows(db: Session, q: str, category: str | None) -> list[dict]:
    stmt = select(Product).where(
        Product.review_status == "active",
        Product.id.not_in(tuple(RETIRED_PRODUCT_IDS)),
    )
    if category:
        stmt = stmt.where(Product.category == category.strip())
    if q:
        t = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(t),
                Product.highlights.ilike(t),
                Product.coverage_summary.ilike(t),
                Product.target_audience.ilike(t),
                Product.clause_summary.ilike(t),
            )
        )
    rows = db.scalars(stmt.order_by(Product.updated_at.desc()).limit(80)).all()
    if rows:
        return [product_to_row(r) for r in rows]
    # Avoid showing demo stubs once the DB has real product rows (e.g. after
    # import with review_status=pending_review / activate script not re-run).
    if (db.scalar(select(func.count()).select_from(Product)) or 0) > 0:
        return []
    return filter_products(q or None, category)


def _semantic_rows(q: str, category: str | None) -> list[dict]:
    pool = load_retrievable_product_rows()
    pool = [r for r in pool if str(r.get("id", "")) not in RETIRED_PRODUCT_IDS]
    if not pool:
        return []
    if category:
        cat = category.strip()
        pool = [r for r in pool if r.get("category") == cat] or pool
    if not q:
        return pool[:30]

    if qdrant_enabled():
        qv = get_embedding_service().embed_texts([q])[0]
        hits = qdrant_search_products(qv, [category] if category else None, limit=30)
        out: list[dict] = []
        for h in hits:
            pl = getattr(h, "payload", None) or {}
            out.append(
                {
                    "id": str(pl.get("id", "")),
                    "name": str(pl.get("name", "")),
                    "category": str(pl.get("category", "")),
                    "summary": str(pl.get("summary", "")),
                    "source_url": str(pl.get("source_url", "")),
                    "is_sample": bool(pl.get("is_sample", False)),
                    "updated_at": str(pl.get("updated_at", "")),
                    "review_status": str(pl.get("review_status", "active")),
                    "match_score": float(getattr(h, "score", 0.0) or 0.0),
                    "match_reason": "vector_qdrant",
                }
            )
        if out:
            return [
                row
                for row in out
                if str(row.get("id", "")) not in RETIRED_PRODUCT_IDS
            ]

    emb = get_embedding_service()
    qv = emb.embed_texts([q])[0]
    texts = [f"{r.get('name', '')} {r.get('summary', '')}" for r in pool]
    vecs = emb.embed_texts(texts)
    scored: list[tuple[float, dict]] = []
    for row, vec in zip(pool, vecs, strict=False):
        score = cosine_similarity(qv, vec)
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            **row,
            "match_score": float(score),
            "match_reason": "vector_local",
        }
        for score, row in scored[:30]
    ]

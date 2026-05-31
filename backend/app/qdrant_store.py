from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import get_settings

logger = logging.getLogger(__name__)


def qdrant_enabled() -> bool:
    return bool((get_settings().qdrant_url or "").strip())


def get_qdrant_client() -> QdrantClient | None:
    if not qdrant_enabled():
        return None
    s = get_settings()
    kwargs: dict[str, Any] = {"url": s.qdrant_url.strip()}
    key = (s.qdrant_api_key or "").strip()
    if key:
        kwargs["api_key"] = key
    return QdrantClient(**kwargs)


def ensure_product_collection(vector_size: int) -> None:
    client = get_qdrant_client()
    if client is None:
        return
    s = get_settings()
    name = s.qdrant_collection_products
    names = {c.name for c in client.get_collections().collections}
    if name not in names:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
        )
        return
    info = client.get_collection(name)
    try:
        vs = int(info.config.params.vectors.size)  # type: ignore[attr-defined]
    except Exception:
        vs = vector_size
    if vs != vector_size:
        logger.warning(
            "qdrant_collection_dimension_mismatch collection=%s expected=%s actual=%s",
            name,
            vector_size,
            vs,
        )


def ensure_memory_collection(vector_size: int) -> None:
    client = get_qdrant_client()
    if client is None:
        return
    s = get_settings()
    name = s.qdrant_collection_memory
    names = {c.name for c in client.get_collections().collections}
    if name in names:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
    )


def upsert_product_points(
    payloads: list[dict[str, Any]],
    vectors: list[list[float]],
) -> None:
    client = get_qdrant_client()
    if client is None:
        return
    s = get_settings()
    name = s.qdrant_collection_products
    points = [
        qm.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, p["id"])), vector=v, payload=p)
        for p, v in zip(payloads, vectors, strict=False)
    ]
    client.upsert(collection_name=name, points=points)


def delete_product_vectors_by_external_ids(external_ids: list[str]) -> None:
    """Drop vectors whose embedding used uuid5(NAMESPACE_URL, product id), matching upsert_product_points."""
    client = get_qdrant_client()
    if client is None or not external_ids:
        return
    s = get_settings()
    name = s.qdrant_collection_products
    point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, pid)) for pid in external_ids]
    try:
        client.delete(collection_name=name, points_selector=qm.PointIdsList(points=point_ids))
        logger.info(
            "qdrant_deleted_product_points collection=%s external_ids=%s",
            name,
            external_ids,
        )
    except Exception:
        logger.exception("qdrant_delete_product_points_failed")
    for pid in external_ids:
        try:
            client.delete(
                collection_name=name,
                points_selector=qm.FilterSelector(
                    filter=qm.Filter(
                        must=[
                            qm.FieldCondition(key="id", match=qm.MatchValue(value=pid)),
                        ]
                    )
                ),
            )
        except Exception:
            logger.exception("qdrant_delete_product_points_payload_failed id=%s", pid)


def search_products(
    vector: list[float],
    category_filters: list[str] | None,
    limit: int = 12,
) -> list[Any]:
    client = get_qdrant_client()
    if client is None:
        return []
    s = get_settings()
    must = [
        qm.FieldCondition(
            key="review_status",
            match=qm.MatchValue(value="active"),
        )
    ]
    flt: qm.Filter | None = None
    if category_filters:
        flt = qm.Filter(
            must=must,
            should=[
                qm.FieldCondition(
                    key="category",
                    match=qm.MatchValue(value=c),
                )
                for c in category_filters
            ]
        )
    else:
        flt = qm.Filter(must=must)
    try:
        res = client.query_points(
            collection_name=s.qdrant_collection_products,
            query=vector,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
        return list(res.points)
    except Exception:
        logger.exception("qdrant_query_products_failed")
        return []


def upsert_memory_points(
    user_id: int,
    conversation_id: int,
    texts: list[str],
    vectors: list[list[float]],
) -> None:
    client = get_qdrant_client()
    if client is None:
        return
    s = get_settings()
    name = s.qdrant_collection_memory
    points = []
    for text, vec in zip(texts, vectors, strict=False):
        pid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{user_id}:{conversation_id}:{text}"))
        payload = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "memory_type": "free_text",
            "text": text,
        }
        points.append(qm.PointStruct(id=pid, vector=vec, payload=payload))
    if points:
        client.upsert(collection_name=name, points=points)


def search_top_memories(
    user_id: int,
    vector: list[float],
    limit: int = 8,
    conversation_id: int | None = None,
) -> list[str]:
    client = get_qdrant_client()
    if client is None:
        return []
    s = get_settings()
    must: list[qm.FieldCondition] = [
        qm.FieldCondition(key="user_id", match=qm.MatchValue(value=user_id)),
    ]
    if conversation_id is not None:
        must.append(
            qm.FieldCondition(
                key="conversation_id",
                match=qm.MatchValue(value=conversation_id),
            )
        )
    flt = qm.Filter(must=must)
    try:
        res = client.query_points(
            collection_name=s.qdrant_collection_memory,
            query=vector,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
        hits = list(res.points)
    except Exception:
        logger.exception("qdrant_query_memory_failed")
        return []
    out: list[str] = []
    for hit in hits:
        pl = getattr(hit, "payload", None) or {}
        t = pl.get("text")
        if isinstance(t, str):
            out.append(t)
    return out

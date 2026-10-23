from __future__ import annotations

import json
import logging
import re
from collections import Counter

from app.embeddings import EmbeddingService, cosine_similarity
from app.product_data import load_retrievable_product_rows
from app.qdrant_store import qdrant_enabled, search_products
from app.schemas import ProductCandidate, ProductRetrievalRequest

logger = logging.getLogger(__name__)


def _excerpt_date_iso(raw: object) -> str | None:
    if raw is None:
        return None
    if hasattr(raw, "isoformat"):
        return str(raw.isoformat())  # type: ignore[union-attr]
    text = str(raw).strip()
    return text or None


def _keyword_slice(stubs: list[dict], req: ProductRetrievalRequest) -> list[dict]:
    needles: list[str] = []
    if req.goals:
        needles.extend(re.findall(r"[\u4e00-\u9fff]{2,}", req.goals))
    if req.profile_summary:
        needles.extend(re.findall(r"[\u4e00-\u9fff]{2,}", req.profile_summary[:800]))
    needles.extend(req.product_categories)
    needles.extend(req.exclusions)
    needles = [n for n in needles if len(n) >= 2]
    counts = Counter(needles)
    top_needles = [w for w, _ in counts.most_common(12)]

    def score_row(row: dict) -> int:
        blob = (row.get("name", "") + row.get("summary", "") + row.get("category", "")).lower()
        return sum(2 if w.lower() in blob else 0 for w in top_needles)

    ranked = sorted(stubs, key=score_row, reverse=True)
    out = [r for r in ranked if score_row(r) > 0]
    return out[:24] if out else stubs[:24]


def _rerank(req: ProductRetrievalRequest, candidates: list[ProductCandidate]) -> list[ProductCandidate]:
    blob = (req.profile_summary + req.goals + " ".join(req.product_categories)).lower()
    scored: list[tuple[float, ProductCandidate]] = []
    for c in candidates:
        bonus = 0.0
        if c.category in req.product_categories:
            bonus += 2.5
        if "预算" in blob or "budget" in blob:
            if "储蓄" in c.category or "储" in c.name:
                bonus += 0.5
        if any(k in blob for k in ("医疗", "医保", "住院")):
            if "医疗" in c.category:
                bonus += 1.5
        if any(k in blob for k in ("重疾", "危疾")):
            if "重疾" in c.category or "危疾" in c.name:
                bonus += 1.5
        if any(k in blob for k in ("人寿", "寿险", "身故")):
            if "人寿" in c.category:
                bonus += 1.5
        if req.risk_appetite and ("保守" in req.risk_appetite):
            if "储蓄" in c.category:
                bonus += 0.6
        scored.append((bonus + c.match_score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


class HybridProductRetriever:
    """Keyword gate + vector similarity; optional Qdrant collection."""

    def __init__(self, embedding: EmbeddingService) -> None:
        self._embedding = embedding

    def retrieve(self, req: ProductRetrievalRequest, limit: int = 12) -> list[ProductCandidate]:
        rows = load_retrievable_product_rows()
        filtered = rows
        if req.product_categories:
            cf = [c.strip() for c in req.product_categories if c.strip()]
            if cf:
                filtered = [s for s in rows if s.get("category") in cf]
                if not filtered:
                    filtered = rows

        narrowed = _keyword_slice(filtered, req)
        semantic_query = (
            f"{req.profile_summary[:600]} \n目标:{req.goals} \n类别:{','.join(req.product_categories)}"
        ).strip()
        if not semantic_query:
            semantic_query = " ".join(p.get("name", "") for p in narrowed[:5])

        query_vec = self._embedding.embed_texts([semantic_query])[0]

        candidates: list[ProductCandidate] = []

        if qdrant_enabled():
            hits = search_products(
                query_vec,
                req.product_categories if req.product_categories else None,
                limit=limit * 2,
            )
            seen: set[str] = set()
            for hit in hits:
                pl = getattr(hit, "payload", None) or {}
                pid = str(pl.get("id", ""))
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                score = float(getattr(hit, "score", 0.0) or 0.0)
                candidates.append(
                    ProductCandidate(
                        product_id=pid,
                        name=str(pl.get("name", "")),
                        category=str(pl.get("category", "")),
                        match_score=score,
                        hit_fields=["vector"],
                        match_reason="向量检索命中（关键词过滤在与请求匹配的集合内）。",
                        source_url=str(pl.get("source_url", "")),
                        updated_at=str(pl.get("updated_at", "")),
                        sum_assured=pl.get("sum_assured"),
                        premium=pl.get("premium"),
                        excerpt_date=_excerpt_date_iso(pl.get("excerpt_date")),
                    )
                )
            if len(candidates) < limit:
                logger.info(
                    "retriever_qdrant_sparse_fallback hits=%s limit=%s",
                    len(candidates),
                    limit,
                )

        if not candidates:
            texts = [(s.get("name", "") + " " + s.get("summary", "")) for s in narrowed]
            if not texts:
                narrowed = filtered[:24]
                texts = [(s.get("name", "") + " " + s.get("summary", "")) for s in narrowed]
            stub_vecs = self._embedding.embed_texts(texts)
            bundle = list(zip(narrowed, stub_vecs, strict=False))
            scored_rows: list[tuple[float, dict]] = []
            for row, sv in bundle:
                sim = cosine_similarity(query_vec, sv)
                hits_kw = []
                blob = row.get("name", "") + row.get("summary", "")
                for tok in set(re.findall(r"[\u4e00-\u9fff]{2,}", semantic_query)):
                    if tok in blob:
                        hits_kw.append(tok)
                scored_rows.append((sim + 0.01 * len(hits_kw), row))
            scored_rows.sort(key=lambda x: x[0], reverse=True)
            for score, row in scored_rows[:limit]:
                hf = ["vector_local"]
                blob = row.get("name", "") + row.get("summary", "")
                extra_kw = [w for w in re.findall(r"[\u4e00-\u9fff]{2,}", semantic_query) if w in blob][:6]
                hf.extend(extra_kw[:4])
                candidates.append(
                    ProductCandidate(
                        product_id=str(row["id"]),
                        name=str(row.get("name", "")),
                        category=str(row.get("category", "")),
                        match_score=float(score),
                        hit_fields=list(dict.fromkeys(hf)),
                        match_reason="关键词裁剪 + 本地向量相似度（Mock 或离线嵌入）。",
                        source_url=str(row.get("source_url", "")),
                        updated_at=str(row.get("updated_at", "")),
                        sum_assured=row.get("sum_assured"),
                        premium=row.get("premium"),
                        excerpt_date=_excerpt_date_iso(row.get("excerpt_date")),
                    )
                )

        candidates = _rerank(req, candidates)
        return candidates[:limit]


def retrieval_request_from_profile(
    profile_summary: str,
    structured: dict | None,
    transcript_tail: str,
) -> ProductRetrievalRequest:
    dims: dict = {}
    cats: list[str] = []
    budget_hint = ""
    risk = ""
    hints: dict = dict(structured or {})
    if structured:
        dims = structured.get("dimensions") or {}
        if isinstance(structured.get("product_focus_categories"), list):
            cats.extend(str(x) for x in structured["product_focus_categories"] if x)
        bh = structured.get("budget_hint")
        if bh:
            budget_hint = str(bh)
        risk = str(dims.get("risk_appetite") or hints.get("risk_appetite") or "")
    goals = transcript_tail[-1200:]
    blob = (profile_summary + goals).lower()
    if not cats:
        if any(k in blob for k in ("医疗", "医保", "住院")):
            cats.append("医疗")
        if any(k in blob for k in ("人寿", "寿险", "身故")):
            cats.append("人寿")
        if any(k in blob for k in ("重疾", "危疾")):
            cats.append("重疾")
        if "储蓄" in blob:
            cats.append("储蓄")
    cats = list(dict.fromkeys(cats))
    goals_dim = dims.get("goals") if isinstance(dims.get("goals"), str) else ""
    merged_goals = goals_dim + "\n" + goals if goals_dim else goals
    return ProductRetrievalRequest(
        profile_summary=profile_summary,
        structured_hints=hints,
        goals=merged_goals.strip(),
        product_categories=cats,
        budget_hint=budget_hint,
        risk_appetite=risk,
        exclusions=[],
    )

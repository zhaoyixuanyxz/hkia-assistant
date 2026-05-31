from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod

from openai import OpenAI

from app.config import Settings, get_settings


def _pseudo_embedding(text: str, dim: int = 1536) -> list[float]:
    """Deterministic fake embedding matching OpenAI small dimension for dev/tests."""
    out: list[float] = []
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    while len(out) < dim:
        seed = hashlib.sha256(seed).digest()
        for b in seed:
            out.append((b / 255.0) * 2.0 - 1.0)
    return out[:dim]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class EmbeddingService(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class MockEmbeddingService(EmbeddingService):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_pseudo_embedding(t) for t in texts]


class OpenAICompatibleEmbeddingService(EmbeddingService):
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        key = (self._settings.embedding_api_key or "").strip()
        base = (self._settings.embedding_api_base or "").strip()
        if not key or not base:
            raise ValueError("embedding_api_key and embedding_api_base required")
        self._client = OpenAI(api_key=key, base_url=base.rstrip("/"))

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(
            model=self._settings.embedding_model,
            input=texts,
        )
        return [d.embedding for d in resp.data]


_default_emb: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Returns OpenAI-compatible embeddings when configured; otherwise deterministic mock."""
    global _default_emb
    s = get_settings()
    key = (s.embedding_api_key or "").strip()
    base = (s.embedding_api_base or "").strip()
    if key and base:
        return OpenAICompatibleEmbeddingService(s)
    if _default_emb is None:
        _default_emb = MockEmbeddingService()
    return _default_emb


def reset_embedding_singleton() -> None:
    global _default_emb
    _default_emb = None

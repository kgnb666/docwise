"""依赖注入：集中构造应用组件，路由层只依赖这里的 get_xxx 函数。

好处：换存储 / 换嵌入实现时只改这一处；
get_pipeline 通过 Depends 接收嵌入器，保证 DI 覆盖（如测试注入）对全链路生效。
"""

from __future__ import annotations

from typing import Protocol

from fastapi import Depends

from app.config import get_settings
from app.core.cache import Cache, InMemoryTTLCache
from app.core.rate_limit import RateLimiter
from app.rag.embedder import Embedder
from app.rag.embedder_hash import HashEmbedder
from app.rag.pipeline import RagPipeline
from app.rag.reranker import NullReranker, OverlapReranker
from app.rag.retriever import Retriever
from app.storage.vector_store import get_vector_store

_settings = get_settings()


class EmbedderLike(Protocol):
    """嵌入器统一接口：openai 与 hash 实现可互换。"""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def get_embedder() -> EmbedderLike:
    if _settings.embedding_provider == "hash":
        return HashEmbedder()
    return Embedder(
        base_url=_settings.embedding_base_url or _settings.openai_base_url,
        api_key=_settings.embedding_api_key or _settings.openai_api_key,
        model=_settings.embedding_model,
    )


def get_reranker():
    if _settings.reranker == "overlap":
        return OverlapReranker(alpha=_settings.rerank_alpha)
    return NullReranker()


def get_retriever() -> Retriever:
    return Retriever(
        vector_store=get_vector_store(),
        top_k=_settings.top_k,
        rerank_top_k=_settings.rerank_top_k,
        alpha=_settings.hybrid_alpha,
        reranker=get_reranker(),
        score_threshold=_settings.score_threshold,
    )


def get_cache() -> Cache | None:
    """检索缓存：开启时返回 TTL 缓存（后续换 Redis 实现，接口不变）。"""
    if not _settings.retrieval_cache_enabled:
        return None
    return InMemoryTTLCache(ttl=_settings.retrieval_cache_ttl)


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """进程级单例限流器。"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            capacity=_settings.rate_limit_capacity,
            refill_per_sec=_settings.rate_limit_refill_per_sec,
        )
    return _rate_limiter


def get_pipeline(embedder: EmbedderLike = Depends(get_embedder)) -> RagPipeline:
    return RagPipeline(
        embedder=embedder,
        retriever=get_retriever(),
        settings=_settings,
        retrieval_cache=get_cache(),
    )

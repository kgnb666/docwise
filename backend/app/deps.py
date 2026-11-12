"""依赖注入：集中构造应用组件，路由层只依赖这里的 get_xxx 函数。

好处：换存储 / 换嵌入实现时只改这一处；
get_pipeline 通过 Depends 接收嵌入器，保证 DI 覆盖（如测试注入）对全链路生效。
"""

from __future__ import annotations

from typing import Annotated, Protocol

import httpx
from fastapi import Depends, Request

from app.api.routes.auth import require_account
from app.config import get_settings
from app.core.cache import Cache, InMemoryTTLCache
from app.core.rate_limit import RateLimiter
from app.rag.embedder import Embedder
from app.rag.embedder_hash import HashEmbedder
from app.rag.pipeline import RagPipeline
from app.rag.reranker import APIReranker, NullReranker, OverlapReranker
from app.rag.retriever import Retriever
from app.storage.accounts import Account
from app.storage.vector_store import VectorStore, get_vector_store
from app.storage.workspace import Workspace

_settings = get_settings()


class EmbedderLike(Protocol):
    """嵌入器统一接口：openai 与 hash 实现可互换。"""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """进程级共享 HTTP 异步客户端，复用连接池（Keep-Alive）。"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=120)
    return _http_client


async def close_http_client() -> None:
    """优雅关闭共享 HTTP 客户端连接池。"""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
    _http_client = None


def reset_http_client() -> None:
    """测试用：重置单例。"""
    global _http_client
    _http_client = None


def get_embedder() -> EmbedderLike:
    if _settings.embedding_provider == "hash":
        return HashEmbedder()
    return Embedder(
        base_url=_settings.embedding_base_url or _settings.openai_base_url,
        api_key=_settings.embedding_api_key or _settings.openai_api_key,
        model=_settings.embedding_model,
        batch_size=_settings.embedding_batch_size,
        client=get_http_client(),
    )


def get_reranker():
    if _settings.reranker == "overlap":
        return OverlapReranker(alpha=_settings.rerank_alpha)
    if _settings.reranker == "api":
        return APIReranker(
            base_url=_settings.rerank_base_url or _settings.embedding_base_url or _settings.openai_base_url,
            api_key=_settings.rerank_api_key or _settings.embedding_api_key or _settings.openai_api_key,
            model=_settings.rerank_model,
            top_n=_settings.rerank_top_n,
        )
    return NullReranker()


def get_retriever(vector_store: VectorStore | None = None) -> Retriever:
    return Retriever(
        vector_store=vector_store if vector_store is not None else get_vector_store(),
        top_k=_settings.top_k,
        rerank_top_k=_settings.rerank_top_k,
        alpha=_settings.hybrid_alpha,
        reranker=get_reranker(),
        score_threshold=_settings.score_threshold,
    )


_cache: Cache | None = None


def get_cache() -> Cache | None:
    """检索缓存：单例，开启时返回 TTL 缓存（后续换 Redis 实现，接口不变）。"""
    global _cache
    if not _settings.retrieval_cache_enabled:
        return None
    if _cache is None:
        _cache = InMemoryTTLCache(ttl=_settings.retrieval_cache_ttl)
    return _cache


def reset_cache() -> None:
    """测试用：重置缓存单例。"""
    global _cache
    _cache = None


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


def get_workspace(request: Request, account: Account = Depends(require_account)) -> Workspace:
    return request.app.state.workspaces.for_account(account.id)


def get_pipeline(
    embedder: EmbedderLike = Depends(get_embedder),
    workspace: Annotated[Workspace | None, Depends(get_workspace)] = None,
) -> RagPipeline:
    return RagPipeline(
        embedder=embedder,
        retriever=get_retriever(workspace.vectors if workspace is not None else None),
        settings=_settings,
        retrieval_cache=workspace.cache if workspace is not None else get_cache(),
        http_client=get_http_client(),
    )

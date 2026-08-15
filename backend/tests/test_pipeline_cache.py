"""Pipeline 检索缓存与改写事件测试（不依赖外部 API）。"""

import asyncio

from app.config import Settings
from app.core.cache import InMemoryTTLCache
from app.rag.pipeline import RagPipeline
from app.rag.retriever import Retriever
from app.storage.vector_store import InMemoryVectorStore


class SpyEmbedder:
    """记录调用次数，返回固定向量。"""

    def __init__(self):
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]


def _make_pipeline(with_cache: bool = True, rewrite: bool = False) -> RagPipeline:
    store = InMemoryVectorStore()
    store.add(
        "c1",
        [0.1, 0.2, 0.3],
        {"doc_id": "d1", "doc_name": "a.md", "index": 0, "text": "苹果 香蕉 机器学习"},
    )
    retriever = Retriever(store, top_k=2, rerank_top_k=2, alpha=0.0)
    settings = Settings(
        embedding_provider="hash",
        query_rewrite_enabled=rewrite,
        agent_enabled=False,
    )
    cache = InMemoryTTLCache(ttl=60) if with_cache else None
    return RagPipeline(SpyEmbedder(), retriever, settings, retrieval_cache=cache)


def test_retrieve_cache_skips_second_embedding():
    p = _make_pipeline(with_cache=True)
    r1 = asyncio.run(p._retrieve("苹果"))
    r2 = asyncio.run(p._retrieve("苹果"))
    assert r1 and r2
    assert p.embedder.calls == 1  # 第二次命中缓存，不再调用 embedding


def test_retrieve_without_cache_calls_every_time():
    p = _make_pipeline(with_cache=False)
    asyncio.run(p._retrieve("苹果"))
    asyncio.run(p._retrieve("苹果"))
    assert p.embedder.calls == 2


def test_query_rewrite_event_emitted_first():
    p = _make_pipeline(with_cache=True, rewrite=True)
    events: list[dict] = []

    async def collect():
        try:
            async for ev in p.stream_answer(
                "它有哪些优点",
                [
                    {"role": "user", "content": "什么是RAG？"},
                    {"role": "assistant", "content": "RAG 是检索增强生成……"},
                ],
            ):
                events.append(ev)
        except RuntimeError:
            pass  # 无 Key 时 LLM 调用会抛错；这里只验证改写事件

    asyncio.run(collect())
    assert events and events[0]["type"] == "query_rewritten"
    assert "什么是RAG" in events[0]["rewritten"]


class _FakeLLM:
    """替代真实 LLM：返回固定 delta，验证 chat 兜底路径。"""

    async def stream_chat(self, messages, tools=None):
        assert "fallback" not in str(messages)  # 占位：messages 应该走常识提示
        yield {"type": "delta", "content": "中秋节是中国的传统节日。"}


def test_fallback_chat_mode_answers_without_knowledge_base():
    """chat 兜底：知识库为空时调用 LLM 常识回答，而不是返回固定文案。"""
    # 空库 pipeline（检索必然无命中）
    settings = Settings(embedding_provider="hash", fallback_mode="chat", agent_enabled=False)
    retriever = Retriever(InMemoryVectorStore(), top_k=2, rerank_top_k=2, alpha=0.0)
    p = RagPipeline(SpyEmbedder(), retriever, settings, retrieval_cache=None)
    p.llm = _FakeLLM()

    events: list[dict] = []

    async def collect():
        async for ev in p.stream_answer("什么是中秋节", []):
            events.append(ev)

    asyncio.run(collect())
    types = [e["type"] for e in events]
    assert types == ["citations", "delta", "done"]
    assert "中秋节" in events[1]["content"]
    assert events[0]["citations"] == []  # 无引用（未命中知识库）

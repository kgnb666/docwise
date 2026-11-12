"""Pipeline 检索缓存与改写事件测试（不依赖外部 API）。"""

import asyncio

import httpx

from app import deps
from app.config import Settings
from app.core.cache import InMemoryTTLCache
from app.rag.pipeline import RagPipeline
from app.rag.retriever import Retriever
from app.storage.vector_store import InMemoryVectorStore, get_vector_store


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


def test_pending_retrieval_cannot_recache_deleted_chunks():
    async def check():
        pipeline = _make_pipeline(with_cache=True)
        rerank_started = asyncio.Event()
        finish_rerank = asyncio.Event()

        class PausedReranker:
            async def rerank(self, query, candidates):
                rerank_started.set()
                await finish_rerank.wait()
                return candidates

        pipeline.retriever.reranker = PausedReranker()
        pending = asyncio.create_task(pipeline._retrieve("苹果"))
        await asyncio.wait_for(rerank_started.wait(), timeout=2)

        assert pipeline.retriever.store.delete_by_doc("d1") == 1
        pipeline.retrieval_cache.clear()
        finish_rerank.set()
        await pending

        assert await pipeline._retrieve("苹果") == []

    asyncio.run(check())


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


class _QueryVectorEmbedder:
    """返回固定查询向量 [1,0,0]，保证粗召回先出 c1，便于验证 rerank 翻盘。"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


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


class _FakeRerankResponse:
    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeRerankClient:
    """替代 httpx.AsyncClient：返回预置 relevance_score，用于验证聊天链路重排。"""

    def __init__(self, response_data: dict):
        self.response_data = response_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        return _FakeRerankResponse(self.response_data)


def test_reranker_api_reorders_citations_in_chat(monkeypatch):
    """reranker=api + mock rerank 响应：聊天链路跑通，候选按 relevance_score 重排。"""
    store = get_vector_store()
    store.clear()
    store.add("c1", [1.0, 0.0, 0.0], {"doc_id": "d1", "doc_name": "a.md", "index": 0, "text": "苹果"})
    store.add("c2", [0.0, 1.0, 0.0], {"doc_id": "d2", "doc_name": "b.md", "index": 0, "text": "机器学习 RAG"})

    client = _FakeRerankClient(
        {
            "results": [
                {"index": 1, "relevance_score": 0.99},
                {"index": 0, "relevance_score": 0.3},
            ]
        }
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: client)
    # 走真实依赖注入：reranker=api 时 get_retriever 自动构造 APIReranker
    monkeypatch.setattr(deps._settings, "reranker", "api")
    monkeypatch.setattr(deps._settings, "rerank_base_url", "https://api.example.com/v1")
    monkeypatch.setattr(deps._settings, "rerank_api_key", "sk-test")
    monkeypatch.setattr(deps._settings, "rerank_top_n", 2)
    # 离线链路：关闭 Agent 工具调用与追问改写，避免真实 LLM 依赖
    monkeypatch.setattr(deps._settings, "agent_enabled", False)
    monkeypatch.setattr(deps._settings, "query_rewrite_enabled", False)

    p = deps.get_pipeline(embedder=_QueryVectorEmbedder())
    p.llm = _FakeLLM()

    result = asyncio.run(p.chat("机器学习", []))
    assert [c["chunk_id"] for c in result["citations"]] == ["c2", "c1"]
    assert result["citations"][0]["score"] == 0.99
    assert "中秋节" in result["answer"]  # 走通 LLM 生成（FakeLLM 固定输出）

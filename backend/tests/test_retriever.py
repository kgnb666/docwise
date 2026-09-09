"""向量存储与混合检索测试（不依赖外部 API，纯本地验证）。"""

import asyncio

from app.rag.reranker import NullReranker
from app.rag.retriever import BM25, Retriever
from app.storage.vector_store import InMemoryVectorStore, cosine_similarity


def test_cosine_similarity():
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == 0.0
    assert abs(cosine_similarity([1, 1], [1, 0]) - 0.7071) < 1e-3


def test_vector_store_add_search_delete():
    store = InMemoryVectorStore()
    store.add("a", [1.0, 0.0], {"text": "苹果"})
    store.add("b", [0.0, 1.0], {"text": "香蕉"})

    hits = store.search([1.0, 0.0], top_k=1)
    assert hits[0]["id"] == "a"

    assert store.count() == 2
    store.delete("a")
    assert store.count() == 1
    assert store.revision >= 2  # 增删都会提升版本号


def test_bm25_ranks_keyword_match_first():
    bm25 = BM25()
    bm25.index(["机器学习是人工智能的一个分支", "今天天气很好适合散步"])
    scores = bm25.scores("机器学习")
    assert scores[0] > scores[1]


def test_hybrid_retrieve_returns_sorted():
    store = InMemoryVectorStore()
    # 手工构造向量：query 语义上更接近 chunk2
    store.add("c1", [1.0, 0.0, 0.0], {"text": "深度学习模型", "doc_id": "d1", "doc_name": "a.md", "index": 0})
    store.add("c2", [0.0, 1.0, 0.0], {"text": "神经网络训练", "doc_id": "d2", "doc_name": "b.md", "index": 0})

    retriever = Retriever(store, top_k=2, rerank_top_k=2, alpha=0.5)
    results = asyncio.run(retriever.retrieve("神经网络", query_vector=[0.0, 1.0, 0.0]))

    assert len(results) == 2
    assert results[0].chunk_id == "c2"
    assert results[0].doc_name == "b.md"


def test_score_threshold_filters_irrelevant():
    store = InMemoryVectorStore()
    store.add("c1", [1.0, 0.0], {"text": "苹果香蕉", "doc_id": "d1", "doc_name": "a.md", "index": 0})
    # 相关度阈值：低相似度结果被过滤 → 空结果（触发兜底）
    retriever = Retriever(store, top_k=2, rerank_top_k=2, alpha=0.0, score_threshold=0.9)
    results = asyncio.run(retriever.retrieve("机器学习", query_vector=[0.0, 1.0]))
    assert results == []

    # 阈值 0：不过滤
    retriever2 = Retriever(store, top_k=2, rerank_top_k=2, alpha=0.0, score_threshold=0.0)
    assert len(asyncio.run(retriever2.retrieve("机器学习", query_vector=[0.0, 1.0]))) == 1


class _AsyncReranker:
    """async 精排器：把检索分低的候选提到最前（模拟云端 relevance_score）。"""

    def __init__(self):
        self.called = False

    async def rerank(self, query: str, candidates: list):
        self.called = True
        # 按候选文本是否包含查询关键词重排：包含的排前面
        return sorted(candidates, key=lambda c: c.text.count(query), reverse=True)


def test_retrieve_awaits_async_reranker():
    store = InMemoryVectorStore()
    store.add("c1", [1.0, 0.0], {"text": "苹果香蕉", "doc_id": "d1", "doc_name": "a.md", "index": 0})
    store.add("c2", [0.0, 1.0], {"text": "机器学习 RAG", "doc_id": "d2", "doc_name": "b.md", "index": 0})

    reranker = _AsyncReranker()
    retriever = Retriever(store, top_k=2, rerank_top_k=2, alpha=0.0, reranker=reranker)
    results = asyncio.run(retriever.retrieve("机器学习", query_vector=[0.0, 1.0]))

    assert reranker.called
    assert results[0].chunk_id == "c2"


def test_retrieve_keeps_sync_reranker_working():
    """兼容回归：默认 NullReranker（同步）在 async retrieve 下仍可用。"""
    store = InMemoryVectorStore()
    store.add("c1", [1.0, 0.0], {"text": "苹果", "doc_id": "d1", "doc_name": "a.md", "index": 0})
    retriever = Retriever(store, top_k=1, rerank_top_k=1, alpha=0.0, reranker=NullReranker())
    results = asyncio.run(retriever.retrieve("苹果", query_vector=[1.0, 0.0]))
    assert [c.chunk_id for c in results] == ["c1"]


def test_in_memory_vector_store_get_all_documents():
    """验证 InMemoryVectorStore.get_all_documents 返回全部文档且返回副本。"""
    store = InMemoryVectorStore()
    store.add("c1", [1.0, 0.0], {"text": "苹果", "doc_id": "d1"})
    docs = store.get_all_documents()
    assert len(docs) == 1
    assert docs[0]["id"] == "c1"
    assert docs[0]["vector"] == [1.0, 0.0]
    assert docs[0]["metadata"]["text"] == "苹果"


class _CustomMockVectorStore:
    """模拟第三方或自定义持久化 VectorStore，不包含 _items 和 _lock 私有属性。"""

    def __init__(self, docs: list[dict]):
        self._docs = docs

    def get_all_documents(self) -> list[dict]:
        return self._docs

    @property
    def revision(self) -> int:
        return 1


def test_retriever_works_with_decoupled_vector_store():
    """验证 Retriever 仅依赖 VectorStore 接口规范，无需 _items 私有属性。"""
    custom_store = _CustomMockVectorStore(
        [
            {"id": "doc_1", "vector": [1.0, 0.0], "metadata": {"text": "自定义存储系统", "doc_id": "d1", "doc_name": "custom.md", "index": 0}}
        ]
    )
    retriever = Retriever(custom_store, top_k=1, rerank_top_k=1, alpha=0.0)
    results = asyncio.run(retriever.retrieve("自定义", query_vector=[1.0, 0.0]))
    assert len(results) == 1
    assert results[0].chunk_id == "doc_1"
    assert results[0].text == "自定义存储系统"


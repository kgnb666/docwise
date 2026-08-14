"""向量存储与混合检索测试（不依赖外部 API，纯本地验证）。"""

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
    results = retriever.retrieve("神经网络", query_vector=[0.0, 1.0, 0.0])

    assert len(results) == 2
    assert results[0].chunk_id == "c2"
    assert results[0].doc_name == "b.md"

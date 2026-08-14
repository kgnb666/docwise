"""Rerank 模块测试。"""

from app.rag.reranker import NullReranker, OverlapReranker, parse_rerank_response
from app.rag.retriever import RetrievedChunk


def _chunk(chunk_id: str, text: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, text=text, doc_id="d1", doc_name="x.md", index=0, score=score
    )


def test_parse_rerank_response_reorders_by_score():
    cs = [
        _chunk("a", "文本a", 0.9),
        _chunk("b", "文本b", 0.6),
        _chunk("c", "文本c", 0.7),
    ]
    data = {
        "results": [
            {"index": 2, "relevance_score": 0.99},
            {"index": 0, "relevance_score": 0.5},
        ]
    }
    out = parse_rerank_response(data, cs)
    assert [c.chunk_id for c in out] == ["c", "a"]
    assert abs(out[0].score - 0.99) < 1e-9


def test_parse_rerank_response_ignores_bad_index():
    cs = [_chunk("a", "文本", 0.5)]
    out = parse_rerank_response({"results": [{"index": 99, "relevance_score": 1.0}]}, cs)
    assert out == []


def test_null_reranker_keeps_order():
    cs = [_chunk("a", "文本", 0.9), _chunk("b", "文本", 0.5)]
    out = NullReranker().rerank("q", cs)
    assert [c.chunk_id for c in out] == ["a", "b"]


def test_overlap_reranker_promotes_relevant():
    # a 检索分高但与查询无关；b 检索分低但与查询高度相关
    cs = [
        _chunk("a", "今天天气很好适合散步", 0.95),
        _chunk("b", "机器学习是人工智能的分支，RAG 是检索增强生成", 0.6),
    ]
    out = OverlapReranker(alpha=0.6).rerank("机器学习 RAG 检索增强", cs)
    assert out[0].chunk_id == "b"


def test_overlap_score_is_jaccard():
    # 英文 token 便于精确断言：交集 2，并集 3 → 2/3
    s = OverlapReranker.overlap_score("apple banana", "apple banana orange")
    assert abs(s - 2 / 3) < 1e-9


def test_reranker_writes_back_score():
    cs = [_chunk("a", "机器学习 RAG", 0.5)]
    out = OverlapReranker(alpha=1.0).rerank("机器学习 RAG", cs)
    # alpha=1.0 时总分完全由重叠分决定
    assert out[0].score > 0.5

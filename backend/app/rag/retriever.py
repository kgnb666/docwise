"""混合检索器：BM25（关键词）+ 向量（语义）加权融合，Rerank 预留接口。

为什么混合？（面试高频题）
- 纯向量检索擅长语义相近，但会漏掉精确关键词匹配（如型号、代码、人名）；
- BM25 擅长精确词匹配，但同义词、改写后就抓瞎；
- 两者分数归一化后加权融合，能同时吃到两边的优势。

Rerank：先粗召回 top_k 个候选，再用更强的模型精排取 rerank_top_k 个。
MVP 阶段 Rerank 为恒等排序（占位），阶段 2 接入 bge-reranker。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.utils import tokenize
from app.rag.reranker import NullReranker
from app.storage.vector_store import VectorStore, cosine_similarity


class BM25:
    """轻量 BM25 实现（无第三方依赖）。

    公式：score(d, q) = Σ idf(t) * tf(t,d)*(k1+1) / (tf(t,d) + k1*(1 - b + b*|d|/avgdl))
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._doc_tokens: list[list[str]] = []
        self._doc_lens: list[int] = []
        self._avgdl: float = 0.0
        self._df: dict[str, int] = {}
        self._idf: dict[str, float] = {}

    def index(self, docs: list[str]) -> None:
        self._doc_tokens = [tokenize(d) for d in docs]
        self._doc_lens = [len(t) for t in self._doc_tokens]
        self._avgdl = sum(self._doc_lens) / len(self._doc_lens) if self._doc_lens else 0.0
        self._df = {}
        for tokens in self._doc_tokens:
            for term in set(tokens):
                self._df[term] = self._df.get(term, 0) + 1
        n = len(self._doc_tokens)
        self._idf = {
            term: math.log((n - df + 0.5) / (df + 0.5) + 1.0)
            for term, df in self._df.items()
        }

    def scores(self, query: str) -> list[float]:
        q_terms = tokenize(query)
        out: list[float] = []
        for i, tokens in enumerate(self._doc_tokens):
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            dl = self._doc_lens[i]
            score = 0.0
            for term in q_terms:
                idf = self._idf.get(term, 0.0)
                if idf == 0.0 or term not in tf:
                    continue
                f = tf[term]
                score += idf * (f * (self.k1 + 1)) / (
                    f + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                )
            out.append(score)
        return out


@dataclass
class RetrievedChunk:
    """检索结果：片段 + 来源 + 分数。"""

    chunk_id: str
    text: str
    doc_id: str
    doc_name: str
    index: int
    score: float
    score_bm25: float = 0.0
    score_vector: float = 0.0


class Retriever:
    def __init__(
        self,
        vector_store: VectorStore,
        top_k: int = 5,
        rerank_top_k: int = 3,
        alpha: float = 0.4,
        reranker=None,
        score_threshold: float = 0.0,
    ):
        self.store = vector_store
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k
        self.alpha = alpha  # 混合权重：alpha 偏向 BM25
        self.reranker = reranker or NullReranker()
        # 相关度阈值：低于则视为"未命中"（进入知识库外兜底分支）
        self.score_threshold = score_threshold
        self._bm25: BM25 | None = None
        self._bm25_revision: int = -1

    # ---------- 内部：BM25 索引按需重建 ----------
    def _ensure_bm25(self) -> BM25:
        rev = self.store.revision
        if self._bm25 is None or self._bm25_revision != rev:
            items = self._all_items()
            texts = [it["metadata"].get("text", "") for it in items]
            bm25 = BM25()
            if texts:
                bm25.index(texts)
            self._bm25 = bm25
            self._bm25_revision = rev
        return self._bm25

    def _all_items(self) -> list[dict]:
        # 内存实现直接全量取；换数据库后这里改成 SELECT 全部
        # 说明：MVP 数据集小，全量扫描可接受；阶段 2 换 FAISS 后向量检索走 ANN。
        store = self.store
        if hasattr(store, "_items"):
            with store._lock:
                return [
                    {"id": k, "metadata": v.metadata, "vector": v.vector}
                    for k, v in store._items.items()
                ]
        raise NotImplementedError("Retriever 目前只支持 InMemoryVectorStore")

    # ---------- 检索主流程 ----------
    def retrieve(self, query: str, query_vector: list[float]) -> list[RetrievedChunk]:
        items = self._all_items()
        if not items:
            return []

        # 1) BM25 分
        bm25 = self._ensure_bm25()
        bm25_scores = bm25.scores(query)

        # 2) 向量分
        vec_scores = [cosine_similarity(query_vector, it["vector"]) for it in items]

        # 3) 归一化（min-max → [0,1]），再按权重融合
        def norm(scores: list[float]) -> list[float]:
            lo, hi = min(scores), max(scores)
            if hi - lo < 1e-9:
                return [0.0] * len(scores)
            return [(s - lo) / (hi - lo) for s in scores]

        nb, nv = norm(bm25_scores), norm(vec_scores)
        combined = [self.alpha * b + (1 - self.alpha) * v for b, v in zip(nb, nv)]

        # 4) 粗召回 top_k
        order = sorted(range(len(items)), key=lambda i: combined[i], reverse=True)[: self.top_k]
        candidates = [
            RetrievedChunk(
                chunk_id=items[i]["id"],
                text=items[i]["metadata"].get("text", ""),
                doc_id=items[i]["metadata"].get("doc_id", ""),
                doc_name=items[i]["metadata"].get("doc_name", ""),
                index=items[i]["metadata"].get("index", 0),
                score=combined[i],
                score_bm25=bm25_scores[i],
                score_vector=vec_scores[i],
            )
            for i in order
        ]

        # 5) Rerank 精排：对粗召回候选重新排序（Null=不重排 / Overlap=轻量重排 / 后续可换 bge-reranker）
        candidates = self.reranker.rerank(query, candidates)

        # 6) 相关度阈值过滤：低于视为"未命中"（触发知识库外兜底）。
        #    注意：必须用原始向量相似度（score_vector，未 min-max 归一化）——
        #    归一化会把小语料里的最高分顶到 1.0，使绝对阈值失效。
        if self.score_threshold > 0:
            candidates = [c for c in candidates if c.score_vector >= self.score_threshold]

        return candidates[: self.rerank_top_k]

"""Rerank 精排模块。

为什么需要 Rerank？（面试高频）
- 粗召回（BM25 + 向量）用的是"轻量打分"，只能保证"相关的大概率在前"；
- Rerank 用更精细的打分对 top-k 候选重新排序，把真正相关的提到最前；
- 经典做法是交叉编码器（bge-reranker），query 与候选拼接后过一遍模型。

本模块：
- NullReranker：恒等排序（不启用时用）；
- OverlapReranker：轻量重叠精排（离线、零依赖），作为 MVP 占位实现；
- APIReranker：调用云上 rerank API（硅基流动 BAAI/bge-reranker-v2-m3），
  免去本地装 torch，接口与本地实现一致（async，适合评测/离线路由）。
"""

from __future__ import annotations

from app.core.utils import tokenize


class NullReranker:
    """不重排：按原分降序。"""

    def rerank(self, query: str, candidates: list) -> list:
        return sorted(candidates, key=lambda c: c.score, reverse=True)


class OverlapReranker:
    """按「查询与候选文本的 token 重叠度（Jaccard）」精排。

    总得分 = (1 - alpha) * 检索分 + alpha * 重叠分
    alpha 越大越强调字面匹配。离线可跑、零依赖，适合快速验证阶段收益。
    """

    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha

    @staticmethod
    def overlap_score(query: str, text: str) -> float:
        q = set(tokenize(query))
        t = set(tokenize(text))
        if not q or not t:
            return 0.0
        inter = len(q & t)
        return inter / (len(q) + len(t) - inter)  # Jaccard

    def rerank(self, query: str, candidates: list) -> list:
        scored = [
            (
                (1 - self.alpha) * c.score
                + self.alpha * self.overlap_score(query, c.text),
                c,
            )
            for c in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        # 把重排分写回候选（score 语义变为「重排后得分」）
        for new_score, c in scored:
            c.score = new_score
        return [c for _, c in scored]


def parse_rerank_response(data: dict, candidates: list) -> list:
    """解析 rerank API 返回：按 relevance_score 降序重排候选。

    输入 data 形如 {"results": [{"index": 0, "relevance_score": 0.98}, ...]}。
    纯函数，便于离线单元测试。
    """
    ordered = []
    for item in sorted(
        data.get("results", []),
        key=lambda x: x.get("relevance_score", 0.0),
        reverse=True,
    ):
        idx = item.get("index", -1)
        if 0 <= idx < len(candidates):
            c = candidates[idx]
            c.score = item.get("relevance_score", c.score)
            ordered.append(c)
    return ordered


class APIReranker:
    """调用云上 rerank API（OpenAI 兼容风格，硅基流动 /v1/rerank）。

    注意：本实现是 async，适合评测脚本与离线批处理；
    运行时接入需把 Retriever.retrieve 改为异步（见 docs/ROADMAP.md 演进项）。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "BAAI/bge-reranker-v2-m3",
        top_n: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.top_n = top_n

    async def rerank(self, query: str, candidates: list) -> list:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/rerank",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "query": query,
                    "documents": [c.text for c in candidates],
                    "top_n": self.top_n,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return parse_rerank_response(data, candidates)

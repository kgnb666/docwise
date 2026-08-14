"""嵌入服务：封装 OpenAI 兼容的 /embeddings 接口。

设计：Embedder 只依赖 base_url / api_key / model 三个配置，
阶段 2 可无缝替换为本地模型（如 bge-small-zh，走 sentence-transformers），
只需保持 `async embed(texts) -> list[list[float]]` 签名不变。
"""

from __future__ import annotations

import httpx

from app.core.retry import with_retry


class Embedder:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。返回顺序与输入一致。网络抖动/限流自动重试。"""
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("未配置 OPENAI_API_KEY，请先在 backend/.env 中填写")

        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": texts},
                )
                resp.raise_for_status()
                return resp.json()

        data = await with_retry(_call)
        # 接口不保证返回顺序，按 index 排序兜底
        by_index = {item["index"]: item["embedding"] for item in data["data"]}
        return [by_index[i] for i in range(len(texts))]

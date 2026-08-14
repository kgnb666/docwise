"""确定性哈希嵌入：无需 API Key 的离线实现。

用途：
- 单元测试 / CI（不依赖外部服务，稳定可复现）；
- 快速原型：没有 Key 也能体验完整检索流程；
- 检索评测：在真实 embedding 上线前先验证检索逻辑。

原理：特征哈希（feature hashing）——把每个 token 用 MD5 哈希到固定维度向量桶，
按奇偶决定正负号，最后 L2 归一化。语义靠 token 重叠体现，质量远不如真实
embedding 模型，但接口与 Embedder 完全一致，随时可切换。
"""

from __future__ import annotations

import hashlib
import math

from app.core.utils import tokenize


class HashEmbedder:
    """与 Embedder 同接口：`async embed(texts) -> list[list[float]]`。"""

    def __init__(self, dim: int = 256):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in tokenize(text):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            out.append(vec)
        return out

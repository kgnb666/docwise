"""向量存储抽象（MVP：内存实现）。

设计目标（面试可讲）：
- 业务代码只依赖 `VectorStore` 接口；
- 数据量上来后换成 FAISS（ANN 索引）或 pgvector / Milvus（持久化 + 多租户），
  只需实现同样的接口，检索器 / 路由层零改动。

线程安全：内存实现用锁保护，未来换数据库实现时锁可去掉。
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度，纯 Python 实现（MVP 阶段避免 numpy 依赖）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class StoredVector:
    id: str
    vector: list[float]
    metadata: dict = field(default_factory=dict)


class VectorStore:
    """接口基类。子类需实现：add / search / delete / count / clear / revision"""

    def add(self, id: str, vector: list[float], metadata: dict | None = None) -> None:
        raise NotImplementedError

    def search(self, vector: list[float], top_k: int = 5) -> list[dict]:
        raise NotImplementedError

    def delete(self, id: str) -> None:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    @property
    def revision(self) -> int:
        """内容版本号：每次增删 +1，供检索器判断是否需要重建索引。"""
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._items: dict[str, StoredVector] = {}
        self._lock = threading.Lock()
        self._revision = 0

    def add(self, id: str, vector: list[float], metadata: dict | None = None) -> None:
        with self._lock:
            self._items[id] = StoredVector(id=id, vector=vector, metadata=metadata or {})
            self._revision += 1

    def search(self, vector: list[float], top_k: int = 5) -> list[dict]:
        with self._lock:
            items = list(self._items.values())
        scored = [
            {"id": it.id, "score": cosine_similarity(vector, it.vector), "metadata": it.metadata}
            for it in items
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete(self, id: str) -> None:
        with self._lock:
            if id in self._items:
                del self._items[id]
                self._revision += 1

    def delete_by_doc(self, doc_id: str) -> int:
        """删除某个文档的全部向量，返回删除条数。"""
        removed = 0
        with self._lock:
            for key in [k for k, v in self._items.items() if v.metadata.get("doc_id") == doc_id]:
                del self._items[key]
                removed += 1
            if removed:
                self._revision += 1
        return removed

    def get_by_doc(self, doc_id: str) -> list[dict]:
        """返回某文档的全部记录（id + metadata），按插入顺序。"""
        with self._lock:
            return [
                {"id": k, "metadata": v.metadata}
                for k, v in self._items.items()
                if v.metadata.get("doc_id") == doc_id
            ]

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._revision += 1

    @property
    def revision(self) -> int:
        return self._revision


# ---- 模块级单例（应用运行期间共享一份数据）----
_store: InMemoryVectorStore | None = None


def get_vector_store() -> InMemoryVectorStore:
    global _store
    if _store is None:
        _store = InMemoryVectorStore()
    return _store


def reset_vector_store() -> None:
    """测试用：重置单例。"""
    global _store
    _store = None

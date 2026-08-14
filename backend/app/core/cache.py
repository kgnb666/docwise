"""缓存抽象（接口先行）。

MVP 用进程内 TTL 缓存；后续换 Redis（支持多实例共享、持久化、过期精确控制）时，
只需实现相同接口：get / set / delete / clear。

用途：检索结果缓存——热点问题命中缓存后跳过 embedding 调用，
节省时间与 API 费用（面试可讲：量化"缓存命中率"与"省了多少调用"）。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any) -> None: ...

    def delete(self, key: str) -> None: ...

    def clear(self) -> None: ...


class InMemoryTTLCache:
    """进程内 TTL 缓存。线程安全；容量满时先清过期项，再驱逐最旧项。"""

    def __init__(self, ttl: float = 300.0, max_size: int = 512):
        self.ttl = ttl
        self.max_size = max_size
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            ts, value = item
            if time.monotonic() - ts > self.ttl:
                del self._data[key]  # 惰性过期
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self.max_size and key not in self._data:
                self._evict_locked()
            self._data[key] = (time.monotonic(), value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def _evict_locked(self) -> None:
        """驱逐：先删过期项；仍满则删最旧（dict 保持插入顺序）。"""
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._data.items() if now - ts > self.ttl]
        for k in expired:
            del self._data[k]
        if len(self._data) >= self.max_size:
            # 删最老的一个
            oldest = next(iter(self._data))
            del self._data[oldest]

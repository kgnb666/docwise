"""令牌桶限流（按 IP 维度）。

为什么需要？（面试可讲）
- 聊天接口会消耗 LLM API 费用，被刷会导致 Key 被限流甚至封禁；
- 令牌桶允许"突发 + 平滑"：容量决定突发上限，补充速率决定长期速率。

MVP 为单进程内存实现；多实例部署时应换 Redis 集中式限流（接口一致）。
"""

from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, capacity: float, refill_per_sec: float):
        assert capacity > 0 and refill_per_sec >= 0
        self.capacity = capacity
        self.refill = refill_per_sec
        self.tokens = capacity
        self.updated = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        # 先按时间补充令牌
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.refill)
        self.updated = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    def __init__(self, capacity: float = 20.0, refill_per_sec: float = 1.0):
        self.capacity = capacity
        self.refill = refill_per_sec
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """key 通常是客户端 IP。返回是否放行。"""
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(self.capacity, self.refill)
                self._buckets[key] = bucket
            return bucket.consume()

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)

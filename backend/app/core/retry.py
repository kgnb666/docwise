"""API 调用重试工具：处理网络抖动与限流（429/5xx）。

为什么需要？（面试可讲）
- 第三方 API 没有 100% 可用性，偶发 429/超时/连接重置；
- 无脑重试会放大故障，指数退避（1s → 2s → 4s）是标准做法；
- 4xx 中只有 429 值得重试（其他 4xx 重试也没用）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def with_retry[T](
    coro_factory: Callable[[], Awaitable[T]],
    retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """执行 coro_factory()，失败按指数退避重试。

    仅对网络错误与可重试状态码（429/5xx）重试；其他异常直接抛出。
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await coro_factory()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in _RETRYABLE_STATUS:
                raise
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc
        if attempt < retries - 1:
            await asyncio.sleep(base_delay * (2**attempt))
    assert last_exc is not None
    raise last_exc

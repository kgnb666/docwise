"""重试工具测试：指数退避、可重试状态码、非重试错误直接抛。"""

import asyncio

import httpx

from app.core.retry import with_retry


def _run(coro_factory) -> object:
    return asyncio.run(coro_factory())


def test_retries_then_succeeds():
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return "ok"

    assert _run(lambda: with_retry(flaky, retries=3, base_delay=0.01)) == "ok"
    assert calls["n"] == 3


def test_non_retryable_status_raised_immediately():
    async def bad() -> None:
        raise httpx.HTTPStatusError(
            "400", request=httpx.Request("GET", "http://x"), response=httpx.Response(400)
        )

    try:
        _run(lambda: with_retry(bad, retries=3, base_delay=0.01))
        assert False, "应当抛出"
    except httpx.HTTPStatusError:
        pass


def test_retryable_status_retried():
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.HTTPStatusError(
                "429", request=httpx.Request("GET", "http://x"), response=httpx.Response(429)
            )
        return "ok"

    assert _run(lambda: with_retry(flaky, retries=2, base_delay=0.01)) == "ok"
    assert calls["n"] == 2

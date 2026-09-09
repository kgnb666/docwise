"""聊天接口限流测试（429）。"""

from fastapi.testclient import TestClient

from app.core.rate_limit import RateLimiter
from app.deps import get_rate_limiter
from app.main import app


def test_chat_rate_limit_returns_429():
    limiter = RateLimiter(capacity=3, refill_per_sec=0)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        client = TestClient(app)
        statuses = []
        for _ in range(5):
            resp = client.post("/api/chat", json={"query": "hi", "history": []})
            statuses.append(resp.status_code)
        # 前 3 次放行（200 兜底或 502 无 Key），后 2 次被限流
        assert statuses.count(429) == 2
        assert statuses[3] == 429
        assert statuses[4] == 429
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)


def test_chat_rate_limit_with_forwarded_for_header():
    """验证通过 X-Forwarded-For 透传不同 IP 时，令牌桶彼此独立隔离。"""
    limiter = RateLimiter(capacity=1, refill_per_sec=0)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        client = TestClient(app)
        # IP 1 发送 2 次，第 2 次触发 429
        resp1 = client.post("/api/chat", json={"query": "hi"}, headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp1.status_code != 429
        resp2 = client.post("/api/chat", json={"query": "hi"}, headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp2.status_code == 429

        # IP 2（多级代理逗号分隔）应该不受 IP 1 耗尽影响
        resp3 = client.post("/api/chat", json={"query": "hi"}, headers={"X-Forwarded-For": "5.6.7.8, 10.0.0.1"})
        assert resp3.status_code != 429
    finally:
        app.dependency_overrides.pop(get_rate_limiter, None)

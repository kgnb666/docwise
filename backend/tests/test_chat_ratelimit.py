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

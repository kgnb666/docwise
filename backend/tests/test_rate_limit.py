"""令牌桶限流测试。"""

import time

from app.core.rate_limit import RateLimiter, TokenBucket


def test_token_bucket_capacity_limited():
    b = TokenBucket(capacity=2, refill_per_sec=0)
    assert b.consume() is True
    assert b.consume() is True
    assert b.consume() is False  # 已耗尽且不补充


def test_token_bucket_refills_over_time():
    b = TokenBucket(capacity=1, refill_per_sec=1000)
    assert b.consume() is True
    time.sleep(0.02)  # 约补充 20 个 token
    assert b.consume() is True


def test_rate_limiter_per_key_isolation():
    rl = RateLimiter(capacity=1, refill_per_sec=0)
    assert rl.allow("ip-a") is True
    assert rl.allow("ip-a") is False
    assert rl.allow("ip-b") is True  # 不同 key 互不影响


def test_reset_single_key():
    rl = RateLimiter(capacity=1, refill_per_sec=0)
    rl.allow("x")
    rl.reset("x")
    assert rl.allow("x") is True

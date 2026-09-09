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


def test_rate_limiter_cleans_expired_buckets():
    # 设置过期时间为 0.05 秒
    rl = RateLimiter(capacity=1, refill_per_sec=0, expiry_seconds=0.05)
    rl.allow("old_key")
    assert "old_key" in rl._buckets
    time.sleep(0.06)
    # 强制让其超过容量或达到时间触发清理
    rl._last_cleanup = 0.0
    rl.allow("new_key")
    assert "old_key" not in rl._buckets
    assert "new_key" in rl._buckets


def test_rate_limiter_evicts_lru_when_reaching_max_keys():
    # 容量设为 2 个 key
    rl = RateLimiter(capacity=1, refill_per_sec=0, max_keys=2, expiry_seconds=1000)
    rl.allow("key1")
    time.sleep(0.01)
    rl.allow("key2")
    assert len(rl._buckets) == 2

    # 再存 key3，应淘汰最久未活跃的 key1
    rl.allow("key3")
    assert len(rl._buckets) == 2
    assert "key1" not in rl._buckets
    assert "key2" in rl._buckets
    assert "key3" in rl._buckets


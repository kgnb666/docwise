"""缓存模块测试。"""

import time

from app.core.cache import InMemoryTTLCache


def test_set_get():
    c = InMemoryTTLCache(ttl=60)
    c.set("k", "v")
    assert c.get("k") == "v"
    assert c.get("missing") is None


def test_expire_after_ttl():
    c = InMemoryTTLCache(ttl=0.05)
    c.set("k", "v")
    time.sleep(0.08)
    assert c.get("k") is None


def test_eviction_drops_oldest_when_full():
    c = InMemoryTTLCache(ttl=60, max_size=2)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)  # 触发驱逐，删最旧的 a
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_delete_and_clear():
    c = InMemoryTTLCache(ttl=60)
    c.set("a", 1)
    c.delete("a")
    assert c.get("a") is None
    c.set("b", 2)
    c.clear()
    assert c.get("b") is None

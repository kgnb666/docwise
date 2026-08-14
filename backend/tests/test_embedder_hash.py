"""哈希嵌入测试：确定性、区分度、维度、L2 归一化。"""

import asyncio

from app.rag.embedder_hash import HashEmbedder


def test_deterministic_same_text_same_vector():
    e = HashEmbedder(dim=64)
    v1 = asyncio.run(e.embed(["机器学习很好"]))[0]
    v2 = asyncio.run(e.embed(["机器学习很好"]))[0]
    assert v1 == v2
    assert len(v1) == 64


def test_different_texts_differ():
    e = HashEmbedder()
    v1 = asyncio.run(e.embed(["苹果香蕉混合检索"]))[0]
    v2 = asyncio.run(e.embed(["docker compose 部署上线"]))[0]
    assert v1 != v2


def test_l2_normalized():
    e = HashEmbedder(dim=128)
    vec = asyncio.run(e.embed(["任意中文句子，用来验证归一化"]))[0]
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_batch_matches_single():
    e = HashEmbedder(dim=32)
    batch = asyncio.run(e.embed(["文本A", "文本B"]))
    single_a = asyncio.run(e.embed(["文本A"]))[0]
    assert batch[0] == single_a

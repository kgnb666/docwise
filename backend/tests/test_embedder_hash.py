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


def test_embedder_batching_slices_correctly():
    """验证 Embedder.embed 能够按 batch_size 自动分片并保序合并。"""
    from app.rag.embedder import Embedder

    embedder = Embedder(
        base_url="https://fake-api", api_key="fake-key", model="fake-model", batch_size=2
    )

    batches: list[list[str]] = []

    async def fake_embed_batch(batch_texts: list[str]) -> list[list[float]]:
        batches.append(batch_texts)
        return [[float(len(t))] for t in batch_texts]

    embedder._embed_batch = fake_embed_batch
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    results = asyncio.run(embedder.embed(texts))

    assert len(results) == 5
    assert results == [[1.0], [2.0], [3.0], [4.0], [5.0]]
    assert len(batches) == 3
    assert batches[0] == ["a", "bb"]
    assert batches[1] == ["ccc", "dddd"]
    assert batches[2] == ["eeeee"]

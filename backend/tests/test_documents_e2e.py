"""端到端接口测试：上传（txt/md/pdf）→ 入库 → 检索 → 列表 → 删除。

全程使用哈希嵌入（无需 API Key），验证完整链路。
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.deps import get_embedder
from app.main import app
from app.rag.embedder_hash import HashEmbedder
from app.rag.retriever import Retriever
from app.storage.document_store import reset_document_store
from app.storage.vector_store import get_vector_store, reset_vector_store

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
RAG_NOTES = (SAMPLES / "rag-notes.md").read_text(encoding="utf-8")
DOCKER_NOTES = (SAMPLES / "docker-notes.md").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolated_store():
    """每个测试用干净的向量库/文档库，并注入哈希嵌入。"""
    reset_vector_store()
    reset_document_store()
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    yield
    app.dependency_overrides.pop(get_embedder, None)
    reset_vector_store()
    reset_document_store()


def _upload(client: TestClient, name: str, content: str, mime: str) -> dict:
    resp = client.post("/api/documents", files={"file": (name, content.encode("utf-8"), mime)})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_upload_list_stats_delete():
    client = TestClient(app)
    data = _upload(client, "rag-notes.md", RAG_NOTES, "text/markdown")
    assert data["chunk_count"] > 0
    doc_id = data["doc_id"]

    stats = client.get("/api/documents/stats").json()
    assert stats["documents"] == 1
    assert stats["chunks"] == data["chunk_count"]

    docs = client.get("/api/documents").json()["documents"]
    assert len(docs) == 1 and docs[0]["doc_id"] == doc_id

    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["removed_chunks"] == data["chunk_count"]
    assert client.get("/api/documents/stats").json()["documents"] == 0


def test_upload_rejects_unknown_ext():
    client = TestClient(app)
    resp = client.post("/api/documents", files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    assert resp.status_code == 400
    assert "暂不支持" in resp.json()["detail"]


def test_list_doc_chunks():
    """分块查看接口：按 index 排序返回全部块。"""
    client = TestClient(app)
    data = _upload(client, "rag-notes.md", RAG_NOTES, "text/markdown")
    doc_id = data["doc_id"]

    resp = client.get(f"/api/documents/{doc_id}/chunks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunk_count"] == data["chunk_count"]
    assert [c["index"] for c in body["chunks"]] == list(range(body["chunk_count"]))
    assert all(c["text"] for c in body["chunks"])

    # 不存在的文档 → 404
    assert client.get("/api/documents/nonexistent/chunks").status_code == 404


def test_retrieval_finds_expected_doc_after_upload():
    """上传两篇文档后，检索结果应命中正确来源。"""
    client = TestClient(app)
    _upload(client, "rag-notes.md", RAG_NOTES, "text/markdown")
    _upload(client, "docker-notes.md", DOCKER_NOTES, "text/markdown")

    embedder = HashEmbedder()
    retriever = Retriever(get_vector_store(), top_k=5, rerank_top_k=3, alpha=0.4)

    qv = asyncio.run(embedder.embed(["Dockerfile 中 CMD 指令的作用"]))[0]
    results = retriever.retrieve("Dockerfile 中 CMD 指令的作用", qv)
    assert results[0].doc_name == "docker-notes.md"

    qv2 = asyncio.run(embedder.embed(["什么是 RAG 检索增强生成"]))[0]
    results2 = retriever.retrieve("什么是 RAG 检索增强生成", qv2)
    assert results2[0].doc_name == "rag-notes.md"

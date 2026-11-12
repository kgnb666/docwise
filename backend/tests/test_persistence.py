"""持久化测试：快照回环 / 重启恢复 / 上传落盘与删除。"""

import asyncio
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.deps import get_embedder
from app.main import app
from app.rag.embedder_hash import HashEmbedder
from app.storage.document_store import get_document_store, reset_document_store
from app.storage.persistence import (
    delete_document_file,
    documents_dir,
    load_all_documents,
    save_document,
)
from app.storage.vector_store import get_vector_store, reset_vector_store

pytestmark = pytest.mark.usefixtures("isolated_api_workspace")

SAMPLE = "这是一篇测试文档。DocWise-X 协议端口是 9801，超时 300ms。"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    reset_vector_store()
    reset_document_store()
    monkeypatch.setattr("app.storage.persistence.data_dir", lambda: tmp_path)
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    yield
    app.dependency_overrides.pop(get_embedder, None)
    reset_vector_store()
    reset_document_store()


def test_save_and_load_roundtrip():
    chunks = [{"index": 0, "text": SAMPLE, "vector": [0.1, 0.2, 0.3]}]
    save_document("doc1", "测试.md", chunks)

    docs = load_all_documents()
    assert len(docs) == 1
    assert docs[0]["doc_id"] == "doc1"
    assert docs[0]["name"] == "测试.md"
    assert docs[0]["chunks"][0]["vector"] == [0.1, 0.2, 0.3]

    assert delete_document_file("doc1") is True
    assert delete_document_file("doc1") is False
    assert load_all_documents() == []


def test_failed_snapshot_replace_preserves_previous_snapshot(monkeypatch):
    chunks = [{"index": 0, "text": SAMPLE, "vector": [0.1, 0.2, 0.3]}]
    path = save_document("doc1", "原始文档.md", chunks)

    def fail_replace(*args):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        save_document("doc1", "修改后的文档.md", chunks)

    assert [doc["name"] for doc in load_all_documents()] == ["原始文档.md"]
    assert list(documents_dir().iterdir()) == [path]


def test_restore_to_stores():
    """模拟重启：写快照 → 清空内存 → 恢复 → 检索命中。"""
    chunks = [{"index": 0, "text": "苹果香蕉", "vector": [1.0, 0.0]},
              {"index": 1, "text": "机器学习", "vector": [0.0, 1.0]}]
    save_document("d2", "笔记.md", chunks)

    reset_vector_store()
    reset_document_store()

    from app.storage.persistence import restore_to_stores

    restored = restore_to_stores(get_vector_store(), get_document_store())
    assert restored == 1
    assert get_document_store().count() == 1
    assert get_vector_store().count() == 2

    # 恢复后能检索到（哈希嵌入风格：直接按向量查）
    hits = get_vector_store().search([1.0, 0.0], top_k=1)
    assert hits[0]["metadata"]["doc_name"] == "笔记.md"


def test_upload_persists_to_disk():
    client = TestClient(app)
    resp = client.post(
        "/api/documents", files={"file": ("测试文档.md", SAMPLE.encode("utf-8"), "text/markdown")}
    )
    assert resp.status_code == 200
    doc_id = resp.json()["doc_id"]

    docs = load_all_documents()
    assert [d["doc_id"] for d in docs] == [doc_id]

    # 删除后快照同步消失
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    assert load_all_documents() == []


def test_upload_failure_keeps_document_out_of_index_and_allows_retry(tmp_path):
    client = TestClient(app, raise_server_exceptions=False)
    files = {"file": ("测试文档.md", SAMPLE.encode("utf-8"), "text/markdown")}
    blocked_directory = tmp_path / "documents"
    blocked_directory.touch()

    failed = client.post("/api/documents", files=files)

    assert failed.status_code == 500
    assert client.get("/api/documents").json() == {"documents": []}
    assert client.get("/api/documents/stats").json() == {"documents": 0, "chunks": 0}

    blocked_directory.unlink()
    retry = client.post("/api/documents", files=files)
    assert retry.status_code == 200
    assert client.get("/api/documents/stats").json() == {"documents": 1, "chunks": 1}
    assert [doc["doc_id"] for doc in load_all_documents()] == [retry.json()["doc_id"]]


def test_delete_failure_keeps_document_available_until_successful_retry(monkeypatch):
    from app.storage.persistence import restore_to_stores

    client = TestClient(app, raise_server_exceptions=False)
    upload = client.post(
        "/api/documents", files={"file": ("测试文档.md", SAMPLE.encode("utf-8"), "text/markdown")}
    )
    assert upload.status_code == 200
    doc_id = upload.json()["doc_id"]
    url = f"/api/documents/{doc_id}"

    def fail_unlink(*args, **kwargs):
        raise PermissionError("simulated unlink failure")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_unlink)
        failed = client.delete(url)

    assert failed.status_code == 500
    assert client.get("/api/documents/stats").json() == {"documents": 1, "chunks": 1}
    assert client.get(f"{url}/chunks").status_code == 200
    assert [doc["doc_id"] for doc in load_all_documents()] == [doc_id]

    assert client.delete(url).status_code == 200
    assert client.get("/api/documents/stats").json() == {"documents": 0, "chunks": 0}
    assert restore_to_stores(get_vector_store(), get_document_store()) == 0


def test_import_kb_persists():
    """import_kb 导入的文档同样落盘。"""
    from pathlib import Path

    from app.rag.embedder_hash import HashEmbedder
    from scripts.import_kb import import_kb

    sample = Path(__file__).resolve().parents[1] / "samples" / "rag-notes.md"
    result = asyncio.run(import_kb([str(sample)], HashEmbedder()))
    assert result["documents"] == 1

    docs = load_all_documents()
    assert len(docs) == 1
    assert docs[0]["name"] == "rag-notes.md"


def test_import_failure_keeps_document_out_of_index(tmp_path):
    from scripts.import_kb import import_kb

    sample = tmp_path / "notes.md"
    sample.write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "documents").touch()

    with pytest.raises(FileExistsError):
        asyncio.run(import_kb([str(sample)], HashEmbedder()))

    assert get_document_store().count() == 0
    assert get_vector_store().count() == 0


def test_restore_preserves_heading_metadata():
    """验证重启从磁盘恢复时，分块的标题层级元数据（heading_path / headings）能够完整保留。"""
    chunks = [
        {
            "index": 0,
            "text": "[核心设计 > 混合检索]\nBM25 结合向量检索",
            "vector": [0.5, 0.5],
            "metadata": {
                "headings": ["核心设计", "混合检索"],
                "heading_path": "核心设计 > 混合检索",
            },
        }
    ]
    save_document("doc_heading", "设计文档.md", chunks)

    reset_vector_store()
    reset_document_store()

    from app.storage.persistence import restore_to_stores

    restored = restore_to_stores(get_vector_store(), get_document_store())
    assert restored == 1

    items = get_vector_store().get_by_doc("doc_heading")
    assert len(items) == 1
    meta = items[0]["metadata"]
    assert meta.get("heading_path") == "核心设计 > 混合检索"
    assert meta.get("headings") == ["核心设计", "混合检索"]
    assert meta.get("doc_name") == "设计文档.md"


def test_restore_preserves_created_at_timestamp():
    """验证重启从磁盘恢复时，文档的原始上传时间（created_at）能够完整保留，而不是被重置为当前时刻。"""
    chunks = [{"index": 0, "text": "内容", "vector": [0.1, 0.2]}]
    custom_time = "2024-01-01 12:00:00"
    save_document("doc_time", "历史文档.md", chunks, created_at=custom_time)

    reset_vector_store()
    reset_document_store()

    from app.storage.persistence import restore_to_stores

    restored = restore_to_stores(get_vector_store(), get_document_store())
    assert restored == 1

    doc = get_document_store().get("doc_time")
    assert doc is not None
    assert doc["created_at"] == custom_time



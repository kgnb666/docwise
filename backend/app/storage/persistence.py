"""磁盘持久化：上传的文档以 JSON 快照保存，重启自动恢复。

为什么这么做（面试可讲）：
- MVP 用内存向量库，重启即失——真实使用场景要求"上传一次，长期可用"；
- 方案：每个文档一份 JSON 快照（分块文本 + 向量 + 元信息），
  启动时扫描 data/documents/ 重新入库（零 API 调用，不花钱）；
- 演进：数据量大了换 pgvector / Milvus（接口不变，见 ARCHITECTURE.md）。

数据目录：backend/data/documents/（已被 .gitignore 排除，不进仓库）。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from app.rag.chunker import Chunk
    from app.storage.document_store import DocumentStore
    from app.storage.vector_store import VectorStore


def data_dir() -> Path:
    """快照根目录（可用 DATA_DIR 环境变量覆盖，测试隔离用）。"""
    settings = get_settings()
    return Path(settings.data_dir)


def documents_dir() -> Path:
    d = data_dir() / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


_lock = threading.Lock()


def _doc_path(doc_id: str, directory: Path | None = None) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", doc_id):
        raise ValueError("文档 ID 格式不正确")
    return (directory if directory is not None else documents_dir()) / f"{doc_id}.json"


def save_document(
    doc_id: str,
    name: str,
    chunks: list[dict],
    created_at: str | None = None,
    *,
    directory: Path | None = None,
) -> Path:
    """保存文档快照。chunks 形如 [{"index": 0, "text": "...", "vector": [...]}]。"""
    payload = {
        "doc_id": doc_id,
        "name": name,
        "chunks": chunks,
        "created_at": created_at or time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    path = _doc_path(doc_id, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = json.dumps(payload, ensure_ascii=False)
    with _lock:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=path.parent,
                prefix=".document-",
                suffix=".tmp",
                encoding="utf-8",
                delete=False,
            ) as temp:
                temp_path = Path(temp.name)
                temp.write(snapshot)
                temp.flush()
                os.fsync(temp.fileno())
            temp_path.replace(path)
        finally:
            if temp_path is not None:
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)
    return path


def persist_and_index_document(
    store: VectorStore,
    doc_store: DocumentStore,
    *,
    doc_id: str,
    name: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
    directory: Path | None = None,
) -> None:
    """快照写入成功后，才将文档发布到内存索引。"""
    chunk_payloads = [
        {"index": chunk.index, "text": chunk.text, "vector": vector, "metadata": chunk.metadata}
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")
    save_document(doc_id, name, chunk_payloads, created_at=created_at, directory=directory)
    _index_document(store, doc_store, doc_id, name, chunk_payloads, created_at)


def delete_document_file(doc_id: str, *, directory: Path | None = None) -> bool:
    """删除文档快照，返回是否存在。"""
    path = _doc_path(doc_id, directory)
    with _lock:
        try:
            path.unlink()
        except FileNotFoundError:
            return False
    return True


def load_all_documents(*, directory: Path | None = None) -> list[dict]:
    """扫描数据目录，返回全部文档快照（doc_id/name/chunks）。"""
    out: list[dict] = []
    directory = directory if directory is not None else documents_dir()
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("chunks"):
                out.append(payload)
        except (json.JSONDecodeError, OSError):
            continue  # 损坏的快照跳过，不阻塞启动
    return out


def _index_document(
    store: VectorStore,
    doc_store: DocumentStore,
    doc_id: str,
    name: str,
    chunks: list[dict],
    created_at: str | None,
) -> None:
    for chunk in chunks:
        store.add(
            f"{doc_id}:{chunk['index']}",
            chunk["vector"],
            {
                "doc_id": doc_id,
                "doc_name": name,
                "index": chunk["index"],
                "text": chunk["text"],
                **chunk.get("metadata", {}),
            },
        )
    doc_store.create(doc_id=doc_id, name=name, chunk_count=len(chunks), created_at=created_at)


def restore_to_stores(
    store: VectorStore, doc_store: DocumentStore, *, directory: Path | None = None
) -> int:
    """把磁盘快照恢复进内存存储，返回恢复的文档数。

    幂等：chunk_id 由 doc_id:index 构成，重复加载不会冲突。
    """
    documents = load_all_documents(directory=directory)
    for payload in documents:
        _index_document(
            store,
            doc_store,
            payload["doc_id"],
            payload["name"],
            payload["chunks"],
            payload.get("created_at"),
        )
    return len(documents)

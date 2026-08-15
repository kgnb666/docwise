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
import threading
from pathlib import Path

from app.config import get_settings


def data_dir() -> Path:
    """快照根目录（可用 DATA_DIR 环境变量覆盖，测试隔离用）。"""
    settings = get_settings()
    return Path(settings.data_dir)


def documents_dir() -> Path:
    d = data_dir() / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


_lock = threading.Lock()


def _doc_path(doc_id: str) -> Path:
    return documents_dir() / f"{doc_id}.json"


def save_document(doc_id: str, name: str, chunks: list[dict]) -> Path:
    """保存文档快照。chunks 形如 [{"index": 0, "text": "...", "vector": [...]}]。"""
    payload = {
        "doc_id": doc_id,
        "name": name,
        "chunks": chunks,
    }
    path = _doc_path(doc_id)
    with _lock:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def delete_document_file(doc_id: str) -> bool:
    """删除文档快照，返回是否存在。"""
    path = _doc_path(doc_id)
    with _lock:
        if path.exists():
            path.unlink()
            return True
        return False


def load_all_documents() -> list[dict]:
    """扫描数据目录，返回全部文档快照（doc_id/name/chunks）。"""
    out: list[dict] = []
    for path in sorted(documents_dir().glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("chunks"):
                out.append(payload)
        except (json.JSONDecodeError, OSError):
            continue  # 损坏的快照跳过，不阻塞启动
    return out


def restore_to_stores(store, doc_store) -> int:
    """把磁盘快照恢复进内存存储，返回恢复的文档数。

    幂等：chunk_id 由 doc_id:index 构成，重复加载不会冲突。
    """
    restored = 0
    for payload in load_all_documents():
        doc_id = payload["doc_id"]
        for chunk in payload["chunks"]:
            store.add(
                f"{doc_id}:{chunk['index']}",
                chunk["vector"],
                {
                    "doc_id": doc_id,
                    "doc_name": payload["name"],
                    "index": chunk["index"],
                    "text": chunk["text"],
                },
            )
        doc_store.create(doc_id=doc_id, name=payload["name"], chunk_count=len(payload["chunks"]))
        restored += 1
    return restored

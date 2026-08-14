"""文档注册表：记录每个文档的元信息（名称、分块数、上传时间等）。

MVP 用内存实现；阶段 2 若需要会话持久化，换成 SQLite / Postgres 表，
接口保持 create / get / list_all / delete 不变。
"""

from __future__ import annotations

import threading
import time


class DocumentStore:
    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(self, doc_id: str, name: str, chunk_count: int, **extra) -> dict:
        doc = {
            "doc_id": doc_id,
            "name": name,
            "chunk_count": chunk_count,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **extra,
        }
        with self._lock:
            self._docs[doc_id] = doc
        return doc

    def get(self, doc_id: str) -> dict | None:
        with self._lock:
            return self._docs.get(doc_id)

    def list_all(self) -> list[dict]:
        with self._lock:
            return list(self._docs.values())

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            return self._docs.pop(doc_id, None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._docs)


_doc_store: DocumentStore | None = None


def get_document_store() -> DocumentStore:
    global _doc_store
    if _doc_store is None:
        _doc_store = DocumentStore()
    return _doc_store


def reset_document_store() -> None:
    global _doc_store
    _doc_store = None

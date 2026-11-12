"""按账号隔离的文档目录、内存索引与检索缓存。"""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from uuid import UUID

from app.config import get_settings
from app.core.cache import Cache, InMemoryTTLCache
from app.storage.accounts import find_account, legacy_adoption
from app.storage.document_store import DocumentStore
from app.storage.persistence import data_dir, load_all_documents, restore_to_stores, save_document
from app.storage.vector_store import InMemoryVectorStore


def account_documents_dir(account_id: str) -> Path:
    return data_dir() / "accounts" / UUID(hex=account_id).hex / "documents"


@dataclass
class Workspace:
    documents: DocumentStore
    vectors: InMemoryVectorStore
    cache: Cache | None
    directory: Path | None


class WorkspaceRegistry:
    def __init__(self) -> None:
        self._workspaces: dict[Path, Workspace] = {}
        self._lock = Lock()

    def for_account(self, account_id: str) -> Workspace:
        directory = account_documents_dir(account_id)
        with self._lock:
            workspace = self._workspaces.get(directory)
            if workspace is None:
                settings = get_settings()
                cache = (
                    InMemoryTTLCache(ttl=settings.retrieval_cache_ttl)
                    if settings.retrieval_cache_enabled
                    else None
                )
                workspace = Workspace(DocumentStore(), InMemoryVectorStore(), cache, directory)
                restore_to_stores(workspace.vectors, workspace.documents, directory=directory)
                self._workspaces[directory] = workspace
            return workspace


def adopt_legacy_documents(username: str) -> int:
    """将无归属快照复制给明确指定的账号，保留源文件。"""
    account = find_account(username)
    if account is None:
        raise ValueError("账号不存在")
    legacy = load_all_documents()
    if not legacy:
        return 0
    directory = account_documents_dir(account.id)
    with legacy_adoption(account) as pending:
        if not pending:
            return 0
        existing = {doc["doc_id"] for doc in load_all_documents(directory=directory)}
        copied = 0
        for doc in legacy:
            doc_id = doc["doc_id"]
            if doc_id in existing:
                continue
            save_document(
                doc_id, doc["name"], doc["chunks"], created_at=doc.get("created_at"), directory=directory
            )
            existing.add(doc_id)
            copied += 1
        return copied

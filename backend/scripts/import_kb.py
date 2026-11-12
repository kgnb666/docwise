"""知识库导入工具：把本地文件/目录批量分块向量化入库。

用法（backend 目录）：
    python scripts/import_kb.py --account alice ../my-notes
    python scripts/import_kb.py --account alice --embedding hash a.pdf b.md c.txt

流程：读取文本 → 分块 → 向量化 → 保存快照 → 写入全局向量库并注册文档。
（重复导入会再次入库；删除请用 API：DELETE /api/documents/{doc_id}）
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from io import TextIOWrapper
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.docx_utils import extract_docx_text
from app.core.pdf_utils import extract_pdf_text
from app.deps import get_embedder
from app.rag.chunker import make_chunks, new_doc_id
from app.storage.accounts import find_account
from app.storage.document_store import DocumentStore, get_document_store
from app.storage.persistence import persist_and_index_document
from app.storage.vector_store import InMemoryVectorStore, get_vector_store
from app.storage.workspace import account_documents_dir

SUPPORTED = {".md", ".markdown", ".txt", ".pdf", ".docx"}


def collect_files(paths: list[str]) -> list[Path]:
    """展开目录/文件参数为支持格式的文件列表。"""
    files: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(
                f
                for f in sorted(path.rglob("*"))
                if f.suffix.lower() in SUPPORTED
                and f.name.lower() != "readme.md"  # 目录说明文档不算知识内容
                and not f.name.startswith(".")
            )
        elif path.is_file() and path.suffix.lower() in SUPPORTED:
            files.append(path)
    return files


def read_text(path: Path) -> str:
    """按扩展名读取纯文本（复用与上传接口一致的解析逻辑）。"""
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path.read_bytes())
    if path.suffix.lower() == ".docx":
        return extract_docx_text(path.read_bytes())
    return path.read_text(encoding="utf-8", errors="ignore")


async def import_kb(
    paths: list[str],
    embedder=None,
    chunk_size: int = 800,
    overlap: int = 100,
    *,
    directory: Path | None = None,
) -> dict:
    """批量导入：返回 {"documents", "chunks", "items"}。"""
    embedder = embedder or get_embedder()
    files = collect_files(paths)
    if not files:
        raise SystemExit(f"未找到支持的文档（{', '.join(sorted(SUPPORTED))}）")

    store = get_vector_store() if directory is None else InMemoryVectorStore()
    doc_store = get_document_store() if directory is None else DocumentStore()
    total_chunks = 0
    imported = []
    for f in files:
        text = read_text(f).strip()
        if not text:
            print(f"  ⚠️ 跳过空文档：{f.name}")
            continue
        doc_id = new_doc_id()
        chunks = make_chunks(text, doc_id=doc_id, doc_name=f.name, chunk_size=chunk_size, overlap=overlap)
        vectors = await embedder.embed([c.text for c in chunks])
        persist_and_index_document(
            store, doc_store, doc_id=doc_id, name=f.name, chunks=chunks, vectors=vectors,
            directory=directory,
        )
        total_chunks += len(chunks)
        imported.append({"name": f.name, "chunks": len(chunks)})
        print(f"  ✅ {f.name}: {len(chunks)} 块")
    return {"documents": len(imported), "chunks": total_chunks, "items": imported}


def main() -> None:
    parser = argparse.ArgumentParser(description="DocWise 知识库导入")
    parser.add_argument("paths", nargs="+", help="文件或目录（递归）")
    parser.add_argument("--account", required=True, help="目标知识库所属账号")
    parser.add_argument("--embedding", choices=["auto", "hash", "openai"], default="auto")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=100)
    args = parser.parse_args()
    account = find_account(args.account)
    if account is None:
        parser.error("账号不存在，请先使用 manage_accounts.py add 创建账号")

    if args.embedding == "hash":
        from app.rag.embedder_hash import HashEmbedder

        embedder = HashEmbedder()
    else:
        embedder = get_embedder()

    result = asyncio.run(import_kb(
        args.paths, embedder, args.chunk_size, args.overlap, directory=account_documents_dir(account.id)
    ))
    print(f"\n导入完成：{result['documents']} 篇文档 / {result['chunks']} 个分块")


if __name__ == "__main__":
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")
    main()

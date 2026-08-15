"""文档接口：上传 / 列表 / 删除 / 统计。

上传流程：解析文本（txt/md/pdf/docx）→ 分块 → 批量向量化 → 入库 → 注册文档元信息。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.docx_utils import extract_docx_text
from app.core.observability import log_event
from app.core.pdf_utils import extract_pdf_text
from app.deps import get_embedder
from app.rag.chunker import make_chunks, new_doc_id
from app.rag.embedder import Embedder
from app.storage.document_store import DocumentStore, get_document_store
from app.storage.vector_store import get_vector_store

router = APIRouter()

# 支持 txt / md / pdf / docx（老式 .doc 需先用 Word 另存为 .docx）
ALLOWED_EXTS = {".txt", ".md", ".markdown", ".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _read_text(ext: str, raw: bytes) -> str:
    """按扩展名解析文件为纯文本。"""
    if ext == ".pdf":
        return extract_pdf_text(raw)
    if ext == ".docx":
        return extract_docx_text(raw)
    return raw.decode("utf-8", errors="ignore")


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    embedder: Embedder = Depends(get_embedder),
    doc_store: DocumentStore = Depends(get_document_store),
) -> dict:
    name = file.filename or "unnamed"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持 {ext} 格式，目前支持：{', '.join(sorted(ALLOWED_EXTS))}",
        )

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 10MB 上限")
    text = _read_text(ext, raw).strip()
    if not text:
        raise HTTPException(status_code=400, detail="文件内容为空（可能是扫描件 PDF，需要 OCR，后续版本支持）")

    # 1) 分块
    doc_id = new_doc_id()
    chunks = make_chunks(text, doc_id=doc_id, doc_name=name)

    # 2) 批量向量化（一次请求嵌入全部块）
    try:
        vectors = await embedder.embed([c.text for c in chunks])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"向量化失败：{exc}") from exc

    # 3) 入库
    store = get_vector_store()
    chunk_payloads = []
    for chunk, vec in zip(chunks, vectors):
        store.add(
            chunk.id,
            vec,
            {
                "doc_id": doc_id,
                "doc_name": name,
                "index": chunk.index,
                "text": chunk.text,
            },
        )
        chunk_payloads.append({"index": chunk.index, "text": chunk.text, "vector": vec})

    # 4) 注册文档 + 落盘持久化（重启自动恢复）
    doc_store.create(doc_id=doc_id, name=name, chunk_count=len(chunks))
    from app.storage.persistence import save_document

    save_document(doc_id, name, chunk_payloads)
    log_event("upload", name=name, chunk_count=len(chunks))
    return {"doc_id": doc_id, "name": name, "chunk_count": len(chunks)}


@router.get("")
async def list_documents(
    doc_store: DocumentStore = Depends(get_document_store),
) -> dict:
    return {"documents": doc_store.list_all()}


@router.get("/stats")
async def stats() -> dict:
    store = get_vector_store()
    doc_store = get_document_store()
    return {"documents": doc_store.count(), "chunks": store.count()}


@router.get("/{doc_id}/chunks")
async def list_doc_chunks(doc_id: str) -> dict:
    """查看某文档的全部分块（调试 / 演示"我的知识被怎么切分"用）。"""
    store = get_vector_store()
    items = store.get_by_doc(doc_id)
    if not items:
        raise HTTPException(status_code=404, detail="文档不存在或尚无分块")
    chunks = sorted(
        (
            {
                "chunk_id": it["id"],
                "index": it["metadata"].get("index", 0),
                "text": it["metadata"].get("text", ""),
            }
            for it in items
        ),
        key=lambda c: c["index"],
    )
    return {"doc_id": doc_id, "chunk_count": len(chunks), "chunks": chunks}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str) -> dict:
    store = get_vector_store()
    doc_store = get_document_store()
    if not doc_store.delete(doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    removed = store.delete_by_doc(doc_id)
    from app.storage.persistence import delete_document_file

    delete_document_file(doc_id)  # 同步删除磁盘快照
    return {"doc_id": doc_id, "removed_chunks": removed}

"""文档接口：上传 / 列表 / 删除 / 统计。

上传流程：解析文本（txt/md/pdf/docx）→ 分块 → 批量向量化 → 入库 → 注册文档元信息。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.docx_utils import extract_docx_text
from app.core.observability import log_event
from app.core.pdf_utils import extract_pdf_text
from app.deps import EmbedderLike, get_embedder, get_workspace
from app.rag.chunker import make_chunks, new_doc_id
from app.storage.persistence import delete_document_file, persist_and_index_document
from app.storage.workspace import Workspace

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
    workspace: Workspace = Depends(get_workspace),
    file: UploadFile = File(...),
    embedder: EmbedderLike = Depends(get_embedder),
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
    try:
        text = _read_text(ext, raw).strip()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"文件解析失败（可能已损坏或格式不兼容）：{exc}"
        ) from exc
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

    # 3) 快照落盘后再发布到索引、注册表和缓存
    persist_and_index_document(
        workspace.vectors,
        workspace.documents,
        doc_id=doc_id,
        name=name,
        chunks=chunks,
        vectors=vectors,
        directory=workspace.directory,
    )
    if workspace.cache is not None:
        workspace.cache.clear()
    log_event("upload", name=name, chunk_count=len(chunks))
    return {"doc_id": doc_id, "name": name, "chunk_count": len(chunks)}


@router.get("")
async def list_documents(workspace: Workspace = Depends(get_workspace)) -> dict:
    return {"documents": workspace.documents.list_all()}


@router.get("/stats")
async def stats(workspace: Workspace = Depends(get_workspace)) -> dict:
    return {"documents": workspace.documents.count(), "chunks": workspace.vectors.count()}


@router.get("/{doc_id}/chunks")
async def list_doc_chunks(doc_id: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    """查看某文档的全部分块（调试 / 演示"我的知识被怎么切分"用）。"""
    items = workspace.vectors.get_by_doc(doc_id)
    if not items:
        raise HTTPException(status_code=404, detail="文档不存在或尚无分块")
    chunks = sorted(
        (
            {
                "chunk_id": it["id"],
                "index": it["metadata"].get("index", 0),
                "text": it["metadata"].get("text", ""),
                "heading_path": it["metadata"].get("heading_path", ""),
                "metadata": {
                    k: v
                    for k, v in it["metadata"].items()
                    if k not in ("index", "text", "doc_id", "doc_name")
                },
            }
            for it in items
        ),
        key=lambda c: c["index"],
    )
    return {"doc_id": doc_id, "chunk_count": len(chunks), "chunks": chunks}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, workspace: Workspace = Depends(get_workspace)) -> dict:
    if workspace.documents.get(doc_id) is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    delete_document_file(doc_id, directory=workspace.directory)
    workspace.documents.delete(doc_id)
    removed = workspace.vectors.delete_by_doc(doc_id)
    if workspace.cache is not None:
        workspace.cache.clear()
    return {"doc_id": doc_id, "removed_chunks": removed}

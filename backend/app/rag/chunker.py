"""文档分块器：标题感知 + 重叠窗口。

分块策略（面试常问）：
1. 优先按段落边界聚合 —— 段落是语义相对完整的单元，避免把一句话拦腰切断；
2. 单个超长段落按字符硬切，并保留 overlap 重叠 —— 防止关键信息恰好落在切缝上；
3. 中文与英文都适用（按字符计数，UTF-8 下 len() 即字符数）。

阶段 2 升级点：按 Markdown 标题（##/###）切分语义块，再对块内做窗口重叠。
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

_SEP_RE = re.compile(r"\n+")


@dataclass
class Chunk:
    """一个检索单元：向量库里每一条记录对应一个 Chunk。"""

    id: str
    text: str
    doc_id: str
    doc_name: str
    index: int
    metadata: dict = field(default_factory=dict)


def split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """把长文本切成有重叠的块，返回纯文本列表。"""
    if not text or not text.strip():
        return []
    if overlap >= chunk_size:
        overlap = chunk_size // 2  # 防止死循环

    paragraphs = [p.strip() for p in _SEP_RE.split(text) if p.strip()]
    chunks: list[str] = []
    buf = ""

    for para in paragraphs:
        # 单段超过上限：先把缓冲区清空，再对长段硬切
        if len(para) > chunk_size:
            if buf:
                chunks.append(buf)
                buf = ""
            start = 0
            while start < len(para):
                end = min(start + chunk_size, len(para))
                chunks.append(para[start:end])
                if end >= len(para):
                    break
                start = end - overlap
            continue

        # 能装下就继续聚合；装不下则换块，并带上重叠衔接
        if not buf or len(buf) + 1 + len(para) <= chunk_size:
            buf = f"{buf}\n{para}" if buf else para
        else:
            if overlap and buf:
                chunks.append(buf)
                buf = buf[-overlap:] + "\n" + para
            else:
                chunks.append(buf)
                buf = para

    if buf:
        chunks.append(buf)
    return chunks


def make_chunks(
    text: str,
    doc_id: str,
    doc_name: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[Chunk]:
    """把整篇文档切成带元信息的 Chunk 列表。"""
    parts = split_text(text, chunk_size, overlap)
    return [
        Chunk(
            id=f"{doc_id}:{i}",
            text=p,
            doc_id=doc_id,
            doc_name=doc_name,
            index=i,
        )
        for i, p in enumerate(parts)
    ]


def new_doc_id() -> str:
    """生成文档 ID（短 uuid，便于阅读）。"""
    return uuid.uuid4().hex[:12]

"""PDF 文本提取（阶段 1 新增）。

为什么单独放一个模块？
- 解析逻辑与上传流程解耦，便于单独测试与替换（未来可换 OCR / 布局解析）；
- pypdf 懒加载：未安装 pypdf 时不影响其他功能。
"""

from __future__ import annotations

import io


def extract_pdf_text(raw: bytes) -> str:
    """从 PDF 字节流提取全部页面文本，页面间以换行拼接。"""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n".join(pages)

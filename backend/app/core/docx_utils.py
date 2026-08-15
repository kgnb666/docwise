"""Word (.docx) 文本提取。

用 python-docx 解析：正文段落 + 表格文本，按文档顺序拼接。
注意：只支持 .docx（Word 2007+ 的 XML 格式）；老式 .doc 二进制格式
python-docx 不支持，需要先用 Word/WPS 另存为 .docx。
"""

from __future__ import annotations

import io

from docx import Document


def extract_docx_text(raw: bytes) -> str:
    """从 .docx 字节流提取全部文本（段落与表格，按出现顺序）。"""
    doc = Document(io.BytesIO(raw))
    parts: list[str] = []

    # 按文档 body 顺序遍历段落与表格（docx 的 XML 顺序）
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for block in doc.element.body.iterchildren():
        if block.tag.endswith("}p"):
            para = Paragraph(block, doc)
            text = para.text.strip()
            if text:
                parts.append(text)
        elif block.tag.endswith("}tbl"):
            table = Table(block, doc)
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))

    return "\n".join(parts)

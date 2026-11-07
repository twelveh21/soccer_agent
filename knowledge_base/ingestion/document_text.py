"""将用户导入的战术资料清洗并切成适合后续 RAG 的文本块。"""

from __future__ import annotations

import re


def normalize_document_text(text: str) -> str:
    """清理文档中的重复空白，得到稳定的纯文本。

    参数：
    - text：从 PDF、TXT 或 Markdown 提取出的原始文本。

    实现逻辑：保留段落边界，将连续空格压缩；空内容返回空字符串，由 Worker 判断导入失败。
    """
    paragraphs = [re.sub(r"[ \t]+", " ", paragraph).strip() for paragraph in text.splitlines()]
    return "\n".join(paragraph for paragraph in paragraphs if paragraph)


def split_document_text(text: str, *, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """按字符窗口切分资料文本，并让相邻块保留少量重叠上下文。

    参数：
    - text：已经清理过的文本。
    - chunk_size：每个切块最大字符数。
    - overlap：相邻切块重复的字符数，防止一句话刚好在边界被截断。

    实现逻辑：优先在换行或句号附近截断；找不到合适边界时按最大长度切分；下一块从截断点减 overlap 继续。
    """
    if chunk_size < 100 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size 必须至少 100，且 overlap 必须大于等于 0 并小于 chunk_size。")
    normalized = normalize_document_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n", start, end), normalized.rfind("。", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]

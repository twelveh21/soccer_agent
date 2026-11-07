"""RAG 文档导入阶段的数据契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class SourceDocument(BaseModel):
    """一份允许进入战术知识库的原始资料。"""

    # source_url 可为空，以支持用户上传的本地材料；license_note 记录使用边界。
    document_id: str
    title: str
    content: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    published_at: datetime | None = None
    license_note: str | None = None


class DocumentChunk(BaseModel):
    """检索系统实际索引的文本块，并保留可追溯的原文定位。"""

    # metadata 用于后续按球队、教练、赛季和资料可信度过滤或重排。
    chunk_id: str
    document_id: str
    text: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)

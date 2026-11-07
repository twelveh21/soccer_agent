"""战术 RAG 检索请求与结果契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    """声明一次可评测的检索意图和限制条件。"""

    # filters 保留赛季、球队、联赛等约束；top_k 受上限控制，避免一次塞入过多上下文。
    query: str = Field(min_length=1)
    top_k: int = Field(default=6, ge=1, le=20)
    filters: dict[str, object] = Field(default_factory=dict)


class RetrievedPassage(BaseModel):
    """供 Solver 使用的证据片段，必须能追溯回原始资料。"""

    # score 是检索分而非事实置信度；citation_id 用于最终回答生成引用。
    citation_id: str
    text: str
    score: float
    metadata: dict[str, object] = Field(default_factory=dict)

"""Temporal 长任务输入和阶段结果的可序列化契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TacticalLearningJob(BaseModel):
    """一次战术资料学习任务的最小输入。"""

    # document_ids 只传数据库 ID，不把 PDF 正文或图片二进制写入 Temporal 历史。
    job_id: str = Field(min_length=1)
    document_ids: list[str] = Field(min_length=1)
    requested_by: str | None = None
    rebuild_index: bool = True
    run_evaluation: bool = True


class TemporalJobResult(BaseModel):
    """长任务完成后返回给 API 或管理页面的安全摘要。"""

    # stages 只记录阶段名和结果摘要，详细文件内容仍由 PostgreSQL/对象存储保存。
    job_id: str
    status: str
    stages: list[dict[str, str]] = Field(default_factory=list)

"""本地 SQLite 记录与外部可观测平台之间的遥测契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """一次节点或工具执行产生的安全遥测事件。"""

    # attributes 只允许安全元数据，例如路由、耗时、模型名和状态，不能放原始网页正文或 API Key。
    run_id: str
    name: str
    status: str
    duration_ms: float | None = None
    attributes: dict[str, object] = Field(default_factory=dict)

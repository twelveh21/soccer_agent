"""研究过程 SSE 事件的供应商无关表示。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResearchStreamEvent(BaseModel):
    """前端可以安全显示的一条工作流进度事件。"""

    # data 只能包含节点名、状态和简短进度，不应向浏览器泄漏内部 Prompt 或第三方密钥。
    event: Literal["run_started", "progress", "node_completed", "needs_human", "final", "error"]
    run_id: str
    data: dict[str, object] = Field(default_factory=dict)

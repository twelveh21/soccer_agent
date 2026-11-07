"""足球 Agent 与记忆、笔记服务之间的最小共享契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """允许保存的稳定偏好、项目笔记或用户明确要求保留的事实。"""

    # 写入由用户显式触发；敏感信息与未经核实的足球结论不得自动进入 memory。
    memory_id: str
    scope: Literal["session", "project", "user"]
    kind: Literal["preference", "note", "episodic"]
    content: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)

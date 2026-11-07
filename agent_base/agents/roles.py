"""多 Agent 角色共享的输入输出契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AgentRoleRequest(BaseModel):
    """角色执行时所需的最小上下文，防止各角色随意读取全局状态。"""

    # question 是用户原始任务；context 只放该角色完成职责所需的已审计材料。
    question: str = Field(min_length=1)
    context: dict[str, object] = Field(default_factory=dict)
    run_id: str = Field(min_length=1)


class AgentRoleResult(BaseModel):
    """角色执行后的统一结果，供 Graph 节点、安全层和观测层共同读取。"""

    # status 区分业务失败与代码异常；warnings 可在最终回答中透明呈现能力边界。
    status: Literal["success", "needs_input", "blocked", "error"]
    payload: dict[str, object] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

"""Agent 运行质量评测的输入与输出契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AgentRunEvalCase(BaseModel):
    """定义一个问题在路由、工具和回答边界上的预期行为。"""

    # 工具要求使用名称而非实现函数，避免替换底层 SDK 时评测用例失效。
    case_id: str
    expected_route: str
    required_nodes: tuple[str, ...]
    allowed_nodes: tuple[str, ...]
    max_solver_attempts: int = Field(default=0, ge=0)
    required_tools: set[str] = Field(default_factory=set)
    allowed_tools: set[str] = Field(default_factory=set)
    requires_citation: bool = False
    requires_limitation_disclosure: bool = False
    max_node_duration_ms: float | None = Field(default=None, gt=0)
    max_model_calls: int | None = Field(default=None, ge=0)
    max_estimated_cost_usd: float | None = Field(default=None, ge=0)


class AgentRunCheck(BaseModel):
    """记录一项过程质量检查的通过情况与原因。"""

    name: str
    status: Literal["pass", "fail", "skip"]
    reason: str


class AgentRunEvaluationReport(BaseModel):
    """汇总单次 Agent 运行的可展示离线评测结果。"""

    # passed 只在所有非 skip 项通过时为真，方便 CI 直接判断是否阻断合并。
    case_id: str
    passed: bool
    checks: list[AgentRunCheck]
    metrics: dict[str, float] = Field(default_factory=dict)

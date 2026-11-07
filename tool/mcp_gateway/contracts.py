"""MCP 安全网关的工具策略、调用请求和审计记录契约。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class McpToolPolicy(BaseModel):
    """定义单个 MCP 工具允许的角色、参数和数值边界。"""

    # allowed_parameters 防止模型暗中追加服务器未设计的危险参数。
    tool_name: str
    allowed_roles: set[str] = Field(default_factory=set)
    allowed_parameters: set[str] = Field(default_factory=set)
    max_query_length: int = Field(default=500, ge=1, le=4_000)
    max_top_k: int = Field(default=5, ge=1, le=20)


class McpCallRequest(BaseModel):
    """Agent 发起一次 MCP 调用前提交给网关的最小信息。"""

    caller_role: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None


class McpAuditRecord(BaseModel):
    """可落库或写入日志的脱敏 MCP 调用审计事件。"""

    tool_name: str
    caller_role: str
    decision: Literal["allow", "deny"]
    reason: str
    run_id: str | None = None

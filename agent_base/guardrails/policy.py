"""可组合的 Agent 安全策略契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PolicyDecision(BaseModel):
    """单项策略的机器可读结论，供 Graph 路由或 API 返回使用。"""

    # allow 继续执行；require_human 触发人工确认；deny 直接拒绝当前动作。
    action: Literal["allow", "require_human", "deny"]
    reason: str
    safe_context: dict[str, object] = Field(default_factory=dict)


def check_research_budget(attempt: int, maximum: int) -> PolicyDecision:
    """判断研究循环是否仍在预设上限内。"""
    # 这条纯函数可先被单元测试，后续再接到 Graph 条件边或模型费用预算。
    if attempt >= maximum:
        return PolicyDecision(action="require_human", reason="研究循环已达到允许上限。")
    return PolicyDecision(action="allow", reason="研究循环仍在允许范围内。")

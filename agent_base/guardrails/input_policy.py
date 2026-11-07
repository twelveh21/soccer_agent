"""进入工作流前的用户输入边界：验证请求，不把它当作模型指令执行。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


InputAction = Literal["allow", "need_clarification", "deny"]
MAX_QUESTION_LENGTH = 4_000


class InputPolicyResult(BaseModel):
    """输入检查的可路由结果，供 Graph 而非模型决定是否继续。"""

    # action 由确定性规则产生，避免把基础输入边界交给模型临场判断。
    action: InputAction
    message: str
    warnings: list[str] = Field(default_factory=list)


def evaluate_question(question: str) -> InputPolicyResult:
    """检查问题是否为空、超长或明显包含试图覆盖系统规则的外部指令。"""
    # 这不是内容审查器；它只阻止会破坏 Agent 边界或无法正常处理的输入形状。
    normalized = question.strip()
    if not normalized:
        return InputPolicyResult(action="need_clarification", message="请告诉我你想查询或研究的足球问题。")
    if len(normalized) > MAX_QUESTION_LENGTH:
        return InputPolicyResult(
            action="need_clarification",
            message=f"问题过长，请压缩到 {MAX_QUESTION_LENGTH} 个字符以内，或先说明最关心的部分。",
        )

    injection_markers = ("忽略之前", "ignore previous", "系统提示词", "system prompt", "开发者指令")
    if any(marker in normalized.lower() for marker in injection_markers):
        return InputPolicyResult(
            action="deny",
            message="我可以帮助处理足球问题，但不能执行要求覆盖系统规则或提取内部提示的内容。请直接描述你想了解的足球信息。",
        )
    return InputPolicyResult(action="allow", message="输入检查通过。")

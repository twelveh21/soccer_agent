"""对 LangGraph 运行轨迹执行确定性、无需模型的工作流评测。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowEvalCase:
    """一条工作流评测用例：输入意图与预期执行轨迹的最小契约。"""

    case_id: str
    question: str
    expected_route: str
    required_nodes: tuple[str, ...]
    allowed_nodes: tuple[str, ...]
    max_solver_attempts: int = 0


def node_names(summary: dict[str, Any]) -> list[str]:
    """从 RunRecorder 摘要中提取成功节点的执行顺序。"""
    # error 事件仍会留在摘要中，但轨迹契约只比较实际成功完成的工作流节点。
    return [
        event["node_name"]
        for event in summary.get("events", [])
        if event.get("status") == "success"
    ]


def is_ordered_subsequence(expected: tuple[str, ...], actual: list[str]) -> bool:
    """判断 required_nodes 是否按顺序出现在实际节点轨迹中。"""
    # 允许未来增加非关键节点，但禁止关键节点顺序被意外改坏。
    actual_iterator = iter(actual)
    return all(any(node == expected_node for node in actual_iterator) for expected_node in expected)


def route_from_summary(summary: dict[str, Any]) -> str | None:
    """从 classify 事件的安全元数据中读取实际路由结果。"""
    # 路由写在节点事件 details 中，而非依赖用户原问题，保持评测数据最小化。
    for event in summary.get("events", []):
        if event.get("node_name") == "classify":
            return event.get("details", {}).get("route")
    return None


def evaluate_workflow_trajectory(
    case: WorkflowEvalCase,
    summary: dict[str, Any],
) -> dict[str, Any]:
    """评估一次运行的路由、关键节点顺序、越权节点与循环次数。"""
    # 评测输出是普通字典，后续可直接写入 JSON、SQLite 或接入 Langfuse score。
    actual_nodes = node_names(summary)
    actual_route = route_from_summary(summary)
    failures: list[str] = []

    route_passed = actual_route == case.expected_route
    if not route_passed:
        failures.append(f"路由错误：期望 {case.expected_route}，实际 {actual_route}。")

    sequence_passed = is_ordered_subsequence(case.required_nodes, actual_nodes)
    if not sequence_passed:
        failures.append(
            f"关键节点顺序错误：期望包含 {list(case.required_nodes)}，实际为 {actual_nodes}。"
        )

    unexpected_nodes = sorted(set(actual_nodes) - set(case.allowed_nodes))
    allowed_nodes_passed = not unexpected_nodes
    if unexpected_nodes:
        failures.append(f"出现未授权节点：{unexpected_nodes}。")

    solver_attempts = actual_nodes.count("solve_research")
    attempts_passed = solver_attempts <= case.max_solver_attempts
    if not attempts_passed:
        failures.append(
            f"Solver 轮次超限：上限 {case.max_solver_attempts}，实际 {solver_attempts}。"
        )

    checks = {
        "route": route_passed,
        "required_node_sequence": sequence_passed,
        "allowed_nodes": allowed_nodes_passed,
        "solver_attempt_limit": attempts_passed,
    }
    return {
        "case_id": case.case_id,
        "passed": all(checks.values()),
        "checks": checks,
        "actual_route": actual_route,
        "actual_nodes": actual_nodes,
        "solver_attempts": solver_attempts,
        "failures": failures,
    }

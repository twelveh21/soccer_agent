"""以脱敏运行摘要评测 Agent 的路由、工具、引用和循环质量。"""

from __future__ import annotations

from typing import Any

from agent_base.evals.workflow_contracts import WorkflowEvalCase, evaluate_workflow_trajectory
from evaluation.agent_quality.contracts import AgentRunCheck, AgentRunEvalCase, AgentRunEvaluationReport
from knowledge_base.citations.validator import validate_citation_ids


def extract_tool_names(summary: dict[str, Any]) -> set[str]:
    """从运行事件中提取本轮实际调用的工具名称。

    参数：summary 是 RunRecorder 输出的脱敏事件摘要。
    实现：读取每个事件 details 中的 tool_name；缺失字段视为该事件不是工具调用，不抛异常中断评测。
    """
    return {
        str(event.get("details", {}).get("tool_name"))
        for event in summary.get("events", [])
        if event.get("details", {}).get("tool_name")
    }


def has_limitation_disclosure(answer: str) -> bool:
    """判断回答是否说明资料边界或不确定性。

    参数：answer 是 Agent 最终回答。
    实现：匹配少量明确中文提示词；这是确定性守门规则，不把措辞优美误当作证据充分。
    """
    markers = ("资料边界", "局限", "无法确认", "需核验", "不确定", "证据不足")
    return any(marker in answer for marker in markers)


def runtime_metrics(summary: dict[str, Any]) -> dict[str, float]:
    """从 RunRecorder 摘要汇总节点耗时、模型次数和可得成本。

    参数：summary 是包含 events 与 model_calls 的单次运行摘要。
    实现：只汇总数值型字段；缺失 Token 或成本不会报错，而是作为零成本已知值和成本可用标记分别返回。
    """
    events = summary.get("events", [])
    model_calls = summary.get("model_calls", [])
    node_duration_ms = sum(float(event.get("duration_ms") or 0) for event in events)
    model_duration_ms = sum(float(call.get("duration_ms") or 0) for call in model_calls)
    known_costs = [call.get("estimated_cost_usd") for call in model_calls]
    return {
        "node_duration_ms": round(node_duration_ms, 2),
        "model_duration_ms": round(model_duration_ms, 2),
        "model_call_count": float(len(model_calls)),
        "estimated_cost_usd": round(sum(float(cost) for cost in known_costs if cost is not None), 8),
        "cost_available": float(bool(model_calls) and all(cost is not None for cost in known_costs)),
    }


def evaluate_runtime_budget(case: AgentRunEvalCase, metrics: dict[str, float]) -> AgentRunCheck:
    """检查一次运行是否满足耗时、模型次数和成本预算。

    参数：case 提供可选预算；metrics 是 runtime_metrics 的汇总结果。
    实现：未配置任何预算时跳过；已配置时逐项比较，并把超限原因合并为一条可行动的失败说明。
    """
    budgets_configured = any(
        value is not None
        for value in (case.max_node_duration_ms, case.max_model_calls, case.max_estimated_cost_usd)
    )
    if not budgets_configured:
        return AgentRunCheck(name="runtime_budget", status="skip", reason="本用例未设置性能或成本预算。")

    failures: list[str] = []
    if case.max_node_duration_ms is not None and metrics["node_duration_ms"] > case.max_node_duration_ms:
        failures.append(f"节点总耗时 {metrics['node_duration_ms']}ms 超过 {case.max_node_duration_ms}ms")
    if case.max_model_calls is not None and metrics["model_call_count"] > case.max_model_calls:
        failures.append(f"模型调用 {int(metrics['model_call_count'])} 次超过 {case.max_model_calls} 次")
    if case.max_estimated_cost_usd is not None:
        if not metrics["cost_available"]:
            failures.append("未取得完整 Token/价格配置，无法验证成本预算")
        elif metrics["estimated_cost_usd"] > case.max_estimated_cost_usd:
            failures.append(f"估算成本 ${metrics['estimated_cost_usd']} 超过 ${case.max_estimated_cost_usd}")
    return AgentRunCheck(
        name="runtime_budget",
        status="pass" if not failures else "fail",
        reason="耗时、调用次数和成本均未超出预算。" if not failures else "；".join(failures) + "。",
    )


def evaluate_agent_run(
    case: AgentRunEvalCase,
    summary: dict[str, Any],
    final_answer: str,
    allowed_citation_ids: set[str],
) -> AgentRunEvaluationReport:
    """对一次完成的 Agent 运行做统一离线质量检查。

    参数：case 是预期行为；summary 是脱敏轨迹；final_answer 是最终文本；allowed_citation_ids 是本轮证据目录。
    实现：复用工作流轨迹评测，再补充工具集合、引用有效性和资料边界检查，最后生成可写入数据库或 CI 的报告。
    """
    trajectory_case = WorkflowEvalCase(
        case_id=case.case_id,
        question="评测输入已脱敏",
        expected_route=case.expected_route,
        required_nodes=case.required_nodes,
        allowed_nodes=case.allowed_nodes,
        max_solver_attempts=case.max_solver_attempts,
    )
    trajectory = evaluate_workflow_trajectory(trajectory_case, summary)
    checks = [
        AgentRunCheck(
            name="workflow_trajectory",
            status="pass" if trajectory["passed"] else "fail",
            reason="工作流路由、节点顺序、节点白名单与循环上限均合规。"
            if trajectory["passed"]
            else "；".join(trajectory["failures"]),
        )
    ]

    actual_tools = extract_tool_names(summary)
    missing_tools = case.required_tools - actual_tools
    unexpected_tools = actual_tools - case.allowed_tools if case.allowed_tools else set()
    tool_passed = not missing_tools and not unexpected_tools
    checks.append(
        AgentRunCheck(
            name="tool_selection",
            status="pass" if tool_passed else "fail",
            reason="工具选择符合用例约束。"
            if tool_passed
            else f"缺少必要工具：{sorted(missing_tools)}；未授权工具：{sorted(unexpected_tools)}。",
        )
    )

    citation_result = validate_citation_ids(final_answer, allowed_citation_ids)
    citation_status = "skip" if not case.requires_citation else ("pass" if citation_result.is_valid and citation_result.cited_ids else "fail")
    checks.append(
        AgentRunCheck(
            name="citation_traceability",
            status=citation_status,
            reason="本用例不要求引用。"
            if citation_status == "skip"
            else "所有引用均可回溯到本轮证据。"
            if citation_status == "pass"
            else f"缺少引用或存在未知引用：{citation_result.unknown_ids}。",
        )
    )

    limitation_ok = has_limitation_disclosure(final_answer)
    limitation_status = "skip" if not case.requires_limitation_disclosure else ("pass" if limitation_ok else "fail")
    checks.append(
        AgentRunCheck(
            name="limitation_disclosure",
            status=limitation_status,
            reason="本用例不要求资料边界说明。"
            if limitation_status == "skip"
            else "回答已说明资料边界。"
            if limitation_status == "pass"
            else "回答缺少资料边界或不确定性说明。",
        )
    )

    metrics = runtime_metrics(summary)
    checks.append(evaluate_runtime_budget(case, metrics))
    passed = all(check.status in {"pass", "skip"} for check in checks)
    return AgentRunEvaluationReport(
        case_id=case.case_id,
        passed=passed,
        checks=checks,
        metrics={
            **metrics,
            "tool_count": float(len(actual_tools)),
            "solver_attempts": float(trajectory["solver_attempts"]),
            "citation_count": float(len(citation_result.cited_ids)),
        },
    )

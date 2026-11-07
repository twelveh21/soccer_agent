"""验证统一 Agent Eval 能检查过程而不调用真实模型。"""

from __future__ import annotations

from evaluation.agent_quality.contracts import AgentRunEvalCase
from evaluation.agent_quality.run_evaluator import evaluate_agent_run


def research_eval_case() -> AgentRunEvalCase:
    """构造一个要求本地战术检索与引用边界的研究评测用例。

    参数：无。
    实现：复用最小研究节点集合，使测试只关注评测器而不依赖真实 Graph 或模型。
    """
    return AgentRunEvalCase(
        case_id="research-with-evidence",
        expected_route="research",
        required_nodes=("classify", "collect_research_evidence", "solve_research", "finalize"),
        allowed_nodes=("classify", "collect_research_evidence", "solve_research", "finalize"),
        max_solver_attempts=1,
        required_tools={"local_tactical_retrieval"},
        allowed_tools={"local_tactical_retrieval"},
        requires_citation=True,
        requires_limitation_disclosure=True,
    )


def test_agent_run_evaluation_passes_a_compliant_trajectory() -> None:
    """合规轨迹、工具、引用和资料边界应共同通过。"""
    # 使用人工摘要确保该测试不会访问 API、模型、数据库或网络。
    summary = {
        "events": [
            {"node_name": "classify", "status": "success", "details": {"route": "research"}},
            {"node_name": "collect_research_evidence", "status": "success", "details": {"tool_name": "local_tactical_retrieval"}},
            {"node_name": "solve_research", "status": "success", "details": {}},
            {"node_name": "finalize", "status": "success", "details": {}},
        ]
    }
    report = evaluate_agent_run(
        research_eval_case(),
        summary,
        "压迫需要协同 [local-foundation:pressing-and-counterpress#0]。\n\n资料边界：具体比赛仍需核验。",
        {"local-foundation:pressing-and-counterpress#0"},
    )
    assert report.passed is True
    assert report.metrics["tool_count"] == 1


def test_agent_run_evaluation_rejects_missing_required_tool() -> None:
    """研究路径未调用必要工具时，评测必须失败。"""
    # 过程评测的价值在于：即使最终文本看起来不错，也能发现 Agent 走错执行路径。
    summary = {
        "events": [
            {"node_name": "classify", "status": "success", "details": {"route": "research"}},
            {"node_name": "collect_research_evidence", "status": "success", "details": {}},
            {"node_name": "solve_research", "status": "success", "details": {}},
            {"node_name": "finalize", "status": "success", "details": {}},
        ]
    }
    report = evaluate_agent_run(
        research_eval_case(),
        summary,
        "压迫需要协同 [local-foundation:pressing-and-counterpress#0]。资料边界：需核验。",
        {"local-foundation:pressing-and-counterpress#0"},
    )
    assert report.passed is False
    assert next(check for check in report.checks if check.name == "tool_selection").status == "fail"


def test_agent_run_evaluation_rejects_an_over_budget_run() -> None:
    """真实运行摘要中的模型调用次数、耗时和成本应可被预算规则限制。"""
    # 以人工摘要模拟 RunRecorder 输出，证明成本控制不依赖真实模型或 API 价格。
    case = research_eval_case().model_copy(
        update={"max_node_duration_ms": 1000, "max_model_calls": 1, "max_estimated_cost_usd": 0.01}
    )
    summary = {
        "events": [
            {"node_name": "classify", "status": "success", "duration_ms": 10, "details": {"route": "research"}},
            {"node_name": "collect_research_evidence", "status": "success", "duration_ms": 20, "details": {"tool_name": "local_tactical_retrieval"}},
            {"node_name": "solve_research", "status": "success", "duration_ms": 1200, "details": {}},
            {"node_name": "finalize", "status": "success", "duration_ms": 10, "details": {}},
        ],
        "model_calls": [
            {"duration_ms": 1000, "estimated_cost_usd": 0.008},
            {"duration_ms": 200, "estimated_cost_usd": 0.008},
        ],
    }
    report = evaluate_agent_run(
        case,
        summary,
        "结论 [local-foundation:pressing-and-counterpress#0]。资料边界：需核验。",
        {"local-foundation:pressing-and-counterpress#0"},
    )
    budget_check = next(check for check in report.checks if check.name == "runtime_budget")
    assert report.passed is False
    assert budget_check.status == "fail"
    assert "模型调用" in budget_check.reason

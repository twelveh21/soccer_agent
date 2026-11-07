"""执行足球 Agent 的无模型费用工作流评测。"""

from __future__ import annotations

import sys
from pathlib import Path

# 直接执行本脚本时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.workflow_routing import classify_route
from agent_base.evals.research_loop_simulator import simulate_research_loop
from agent_base.evals.workflow_contracts import WorkflowEvalCase, evaluate_workflow_trajectory
from agent_base.evals.workflow_dataset import RESEARCH_LOOP_EVAL_CASES, WORKFLOW_EVAL_CASES


def run_route_evaluations() -> list[dict[str, str | bool]]:
    """对固定问题集执行路由评测，不调用模型、工具或网络。"""
    # 路由是 Agent 成本与质量的第一道门，因此先将其做成快速、可重复的回归检查。
    results = []
    for case in WORKFLOW_EVAL_CASES:
        actual_route = classify_route(case.question)
        results.append(
            {
                "case_id": case.case_id,
                "expected_route": case.expected_route,
                "actual_route": actual_route,
                "passed": actual_route == case.expected_route,
            }
        )
    return results


def research_loop_contract_case(case_id: str) -> WorkflowEvalCase:
    """为研究循环模拟生成统一的轨迹契约。"""
    # allowlist 覆盖完整研究分支；required_nodes 只要求所有成功路径均必经的节点。
    return WorkflowEvalCase(
        case_id=case_id,
        question="离线研究循环模拟",
        expected_route="research",
        required_nodes=(
            "classify",
            "plan_research",
            "collect_research_evidence",
            "solve_research",
            "reflect_research",
            "verify_evidence",
            "finalize",
        ),
        allowed_nodes=(
            "classify",
            "plan_research",
            "collect_research_evidence",
            "solve_research",
            "reflect_research",
            "verify_evidence",
            "finalize",
        ),
        max_solver_attempts=2,
    )


def run_research_loop_evaluations() -> list[dict[str, object]]:
    """执行无模型研究回环评测，验证补证、重规划和最大轮次。"""
    # 每个 case 只替代 Critic verdict；节点选择仍由生产路由函数决定。
    results = []
    for case_id, verdicts in RESEARCH_LOOP_EVAL_CASES:
        summary = simulate_research_loop(verdicts)
        result = evaluate_workflow_trajectory(
            research_loop_contract_case(case_id), summary
        )
        result["verdicts"] = list(verdicts)
        results.append(result)
    return results


def main() -> None:
    """在命令行输出路由评测汇总，并以失败状态阻止错误规则进入下一步。"""
    # 未来会扩展为执行真实运行、读取 RunRecorder 摘要并调用 evaluate_workflow_trajectory。
    route_results = run_route_evaluations()
    loop_results = run_research_loop_evaluations()
    results = [*route_results, *loop_results]
    failed_cases = [result for result in results if not result["passed"]]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        detail = result.get("actual_route", result.get("verdicts"))
        print(f"[{status}] {result['case_id']}：{detail}")
    if failed_cases:
        raise SystemExit(f"路由评测失败：{len(failed_cases)} 项。")
    print(f"工作流评测通过：{len(results)} / {len(results)}")


if __name__ == "__main__":
    main()

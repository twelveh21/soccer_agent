"""工作流评测器和固定路由评测集的离线测试。"""

import sys
from pathlib import Path

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.evals.run_offline_evals import (
    run_research_loop_evaluations,
    run_route_evaluations,
)
from agent_base.evals.workflow_contracts import WorkflowEvalCase, evaluate_workflow_trajectory


def check_route_dataset() -> None:
    """验证固定问题集当前全部被路由到预期路径。"""
    # 此测试只执行纯规则函数，适合每次改动路由关键词后快速回归。
    assert all(result["passed"] for result in run_route_evaluations())


def check_trajectory_contract() -> None:
    """验证轨迹评测能识别成功路径与 Solver 超轮次。"""
    # 使用人工构造的安全摘要，避免真实模型、工具和 SQLite 状态影响评测稳定性。
    case = WorkflowEvalCase(
        case_id="research-contract",
        question="示例战术问题",
        expected_route="research",
        required_nodes=("classify", "plan_research", "solve_research", "finalize"),
        allowed_nodes=("classify", "plan_research", "solve_research", "finalize"),
        max_solver_attempts=2,
    )
    valid_summary = {
        "events": [
            {"node_name": "classify", "status": "success", "details": {"route": "research"}},
            {"node_name": "plan_research", "status": "success", "details": {}},
            {"node_name": "solve_research", "status": "success", "details": {}},
            {"node_name": "finalize", "status": "success", "details": {}},
        ]
    }
    assert evaluate_workflow_trajectory(case, valid_summary)["passed"] is True

    over_budget_summary = {
        "events": valid_summary["events"][:3]
        + [
            {"node_name": "solve_research", "status": "success", "details": {}},
            {"node_name": "solve_research", "status": "success", "details": {}},
            {"node_name": "finalize", "status": "success", "details": {}},
        ]
    }
    result = evaluate_workflow_trajectory(case, over_budget_summary)
    assert result["passed"] is False
    assert result["checks"]["solver_attempt_limit"] is False


def check_research_loop_dataset() -> None:
    """验证四类 Critic 决定都会生成合规且有上限的研究轨迹。"""
    # 这一层比单测 choose_after_reflection 更接近整条 Graph：检查节点序列与循环次数。
    results = run_research_loop_evaluations()
    assert len(results) == 4
    assert all(result["passed"] for result in results)

    capped = next(result for result in results if result["case_id"] == "research-cap-gather-more")
    assert capped["solver_attempts"] == 2


def main() -> None:
    """作为独立脚本运行工作流评测测试。"""
    # 将数据集与轨迹契约一同回归，防止改图时只改了路由或只改了测试之一。
    check_route_dataset()
    check_trajectory_contract()
    check_research_loop_dataset()
    print("工作流评测测试通过")


if __name__ == "__main__":
    main()

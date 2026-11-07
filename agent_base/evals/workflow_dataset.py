"""足球 Agent 第一版离线路由与轨迹评测集。"""

from agent_base.evals.workflow_contracts import WorkflowEvalCase
from agent_base.evals.research_loop_simulator import CriticVerdict


# 基础题、实时题和战术研究题都要覆盖，避免只在一种输入上优化路由规则。
WORKFLOW_EVAL_CASES: tuple[WorkflowEvalCase, ...] = (
    WorkflowEvalCase(
        case_id="basic-premier-league-standings",
        question="英超积分榜",
        expected_route="basic_data",
        required_nodes=("classify", "basic_data", "verify_evidence", "finalize"),
        allowed_nodes=("classify", "basic_data", "verify_evidence", "finalize"),
    ),
    WorkflowEvalCase(
        case_id="current-injury-news",
        question="阿森纳最新伤停新闻",
        expected_route="current_info",
        required_nodes=("classify", "current_info", "verify_evidence", "finalize"),
        allowed_nodes=("classify", "current_info", "verify_evidence", "finalize"),
    ),
    WorkflowEvalCase(
        case_id="research-wide-attacks",
        question="分析阿森纳如何利用边路宽度破解低位防守",
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
    ),
)


RESEARCH_LOOP_EVAL_CASES: tuple[tuple[str, tuple[CriticVerdict, ...]], ...] = (
    # 一次通过是研究路径最短且最常见的成功轨迹。
    ("research-pass-first-attempt", ("pass",)),
    # Critic 要求补证后，必须回到 Collector，而不是直接让 Solver 重写草案。
    ("research-gather-more-then-pass", ("gather_more", "pass")),
    # 原计划有问题时，必须经过 Planner 后再收集新一轮材料。
    ("research-replan-then-pass", ("replan", "pass")),
    # 即使 Critic 继续要求补证，达到硬上限也必须结束，避免成本失控。
    ("research-cap-gather-more", ("gather_more", "gather_more")),
)

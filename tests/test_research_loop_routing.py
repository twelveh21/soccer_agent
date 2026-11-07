"""研究反思循环的 LangGraph 条件路由测试。"""

import sys
from pathlib import Path

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.workflow_routing import RESEARCH_MAX_SOLVE_ATTEMPTS, choose_after_reflection


def make_state(verdict: str, attempt: int) -> dict[str, object]:
    """构造路由函数需要的最小状态，避免测试触发真实模型或工具调用。"""
    # 路由器只读取 review.verdict 与 research_attempt，因此测试不需要完整 SoccerAgentState。
    return {"review": {"verdict": verdict}, "research_attempt": attempt}


def check_reflection_loop_routing() -> None:
    """验证三种 Critic 决定和最大轮次上限会路由到正确节点。"""
    # pass 直接收尾，gather_more 回 Solver，replan 回 Planner。
    assert choose_after_reflection(make_state("pass", 1)) == "verify"
    assert choose_after_reflection(make_state("gather_more", 1)) == "gather_more"
    assert choose_after_reflection(make_state("replan", 1)) == "replan"

    # 即使 Critic 还想继续，达到硬上限后也必须收尾，避免无限循环与成本失控。
    assert (
        choose_after_reflection(make_state("gather_more", RESEARCH_MAX_SOLVE_ATTEMPTS))
        == "verify"
    )
    assert (
        choose_after_reflection(make_state("replan", RESEARCH_MAX_SOLVE_ATTEMPTS))
        == "verify"
    )


def main() -> None:
    """作为独立脚本运行研究循环条件路由测试。"""
    # 与其他测试保持同样的直接执行入口，便于逐步理解 Graph 行为。
    check_reflection_loop_routing()
    print("研究反思循环路由测试通过")


if __name__ == "__main__":
    main()

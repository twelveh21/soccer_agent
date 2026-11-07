"""无模型模拟研究路径的 Critic 回环，用于验证 LangGraph 路由契约。"""

from __future__ import annotations

from typing import Any, Literal

from agent_base.workflow_routing import RESEARCH_MAX_SOLVE_ATTEMPTS, choose_after_reflection

CriticVerdict = Literal["pass", "gather_more", "replan"]


def successful_event(node_name: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """构造一条与 RunRecorder 摘要兼容的成功节点事件。"""
    # 离线模拟不写 SQLite；沿用摘要结构即可复用真实运行的轨迹评测器。
    return {
        "node_name": node_name,
        "status": "success",
        "details": details or {},
    }


def simulate_research_loop(verdicts: tuple[CriticVerdict, ...]) -> dict[str, Any]:
    """按给定 Critic verdict 序列模拟一条完整研究工作流摘要。"""
    # 这不是伪造模型结果来“通过测试”；它只替代模型输出 verdict，真实调用图中的路由函数。
    if not verdicts:
        raise ValueError("研究循环评测至少需要提供一个 Critic verdict。")

    events = [
        successful_event("classify", {"route": "research"}),
        successful_event("plan_research"),
    ]
    attempt = 0
    verdict_index = 0

    while True:
        # 每一次求解前都必须先收集证据，保证 Collector 不会被 Critic 循环绕过。
        events.append(successful_event("collect_research_evidence"))
        events.append(successful_event("solve_research"))
        attempt += 1

        # 如果脚本 verdict 已耗尽，视为评测用例本身配置错误，而非悄悄默认 pass。
        if verdict_index >= len(verdicts):
            raise ValueError("Critic verdict 序列不足以让研究循环结束。")
        verdict = verdicts[verdict_index]
        verdict_index += 1
        events.append(successful_event("reflect_research", {"verdict": verdict}))

        # 调用真实路由逻辑，确保上限策略与生产 Graph 使用同一份代码。
        next_step = choose_after_reflection(
            {"review": {"verdict": verdict}, "research_attempt": attempt}
        )
        if next_step == "verify":
            events.extend(
                [successful_event("verify_evidence"), successful_event("finalize")]
            )
            break
        if next_step == "gather_more":
            continue

        # replan 必须回到 Planner，再重新收集证据和求解。
        events.append(successful_event("plan_research"))

    return {
        "status": "success",
        "events": events,
        "research_attempts": attempt,
        "max_attempts": RESEARCH_MAX_SOLVE_ATTEMPTS,
    }

"""验证 Human-in-the-loop 的触发范围与恢复后状态更新。"""

from __future__ import annotations

from agent_base.human_loop import build_clarification_request


def test_human_loop_only_interrupts_ambiguous_match_analysis() -> None:
    """“这场比赛的战术”应追问，但一般战术概念问题不应被打断。"""
    # 追问过多会破坏产品体验，因此规则刻意收窄到指代性具体比赛研究。
    request = build_clarification_request("分析一下这场比赛的压迫战术")
    assert request is not None
    assert "对阵双方" in request.missing_fields
    assert build_clarification_request("高位压迫的基本原则是什么") is None

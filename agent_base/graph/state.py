"""LangGraph 共享状态的唯一数据字典与初始化入口。"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from agent_base.workflow_routing import RouteName


class SoccerAgentState(TypedDict):
    """一次足球问题从输入到输出期间在节点间流转的全部业务状态。"""

    # question 是用户任务；session_id 用于恢复同一会话；run_id 用于观测、复盘和错误定位。
    question: str
    session_id: str
    run_id: str
    input_policy: dict[str, Any]
    route: RouteName
    evidence: Annotated[list[dict[str, Any]], operator.add]
    warnings: Annotated[list[str], operator.add]
    needs_web_fallback: bool
    verification: dict[str, Any]
    plan: dict[str, Any]
    collected_evidence: list[dict[str, Any]]
    draft: str
    review: dict[str, Any]
    research_attempt: int
    answer_draft: str
    final_answer: str
    human_clarification: str


def build_initial_state(question: str, session_id: str, run_id: str) -> SoccerAgentState:
    """为每次 Graph 调用创建字段完整、可审计且不会跨请求复用的初始状态。"""
    # 所有可变容器都在函数内新建，避免不同用户请求意外共享证据、警告或审阅结果。
    return {
        "question": question,
        "session_id": session_id,
        "run_id": run_id,
        "input_policy": {},
        "route": "basic_data",
        "evidence": [],
        "warnings": [],
        "needs_web_fallback": False,
        "verification": {},
        "plan": {},
        "collected_evidence": [],
        "draft": "",
        "review": {},
        "research_attempt": 0,
        "answer_draft": "",
        "final_answer": "",
        "human_clarification": "",
    }

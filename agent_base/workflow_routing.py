"""足球 Agent 的纯路由策略：不依赖模型、工具或数据库。"""

from __future__ import annotations

from typing import Any, Literal


RouteName = Literal["basic_data", "current_info", "research"]
RESEARCH_MAX_SOLVE_ATTEMPTS = 2


def classify_route(question: str) -> RouteName:
    """用低成本、可解释的规则把问题分到三条工作流路径。"""
    # 战术研究优先级最高，避免“战术新闻”等复杂问题被错误送进简单网页查询。
    research_markers = (
        "战术", "分析", "复盘", "为什么", "如何", "对比", "比较", "研究", "逼抢",
        "阵型", "打法", "优势", "弱点", "建议", "预测",
    )
    if any(marker in question for marker in research_markers):
        return "research"

    # 实时性强、或基础 API 当前不适合覆盖的领域，优先走网页信息路径。
    current_info_markers = (
        "伤停", "转会", "新闻", "发布会", "采访", "即时", "实时", "首发", "换人",
        "红牌", "黄牌", "中超", "日职", "j联赛", "mls",
    )
    if any(marker in question.lower() for marker in current_info_markers):
        return "current_info"

    # 其余问题默认是赛程、积分榜、阵容、球员资料等结构化基础数据查询。
    return "basic_data"


def choose_after_reflection(state: dict[str, Any]) -> Literal["verify", "gather_more", "replan"]:
    """根据 Critic verdict 和硬上限，选择验证、补证或重新规划。"""
    # 硬上限先于模型 verdict 生效，保证模型无法把工作流推入无界循环。
    verdict = state["review"]["verdict"]
    if verdict == "pass" or state["research_attempt"] >= RESEARCH_MAX_SOLVE_ATTEMPTS:
        return "verify"
    if verdict == "gather_more":
        return "gather_more"
    return "replan"

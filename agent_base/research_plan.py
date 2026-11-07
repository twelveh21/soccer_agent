"""足球战术研究工作流使用的结构化规划数据模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceKind = Literal["basic_data", "web_search", "tactical_rag", "authoritative_tactical_web", "user_material"]


class ResearchSubQuestion(BaseModel):
    """一项可独立收集证据并由 Solver 回答的研究子问题。"""

    # 禁止模型偷偷添加未定义字段，保证后续收集节点只处理约定好的任务契约。
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=5, max_length=160, description="待验证的具体问题")
    purpose: str = Field(min_length=5, max_length=160, description="该问题如何支撑最终研究结论")
    required_sources: list[SourceKind] = Field(
        min_length=1,
        max_length=3,
        description="回答该问题必须收集的资料类别",
    )


class ResearchPlan(BaseModel):
    """Planner 的受约束输出，也是后续 Agent 节点之间的稳定接口。"""

    # 结构化模型让 Planner 的输出可验证、可持久化，也可直接成为将来的评测对象。
    model_config = ConfigDict(extra="forbid")

    research_goal: str = Field(min_length=8, max_length=240, description="本次研究要回答的核心目标")
    sub_questions: list[ResearchSubQuestion] = Field(
        min_length=2,
        max_length=4,
        description="按逻辑顺序排列的研究子问题",
    )
    completion_criteria: list[str] = Field(
        min_length=2,
        max_length=4,
        description="什么条件下可以认为证据足以形成回答",
    )
    assumptions_or_gaps: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="当前无法确认、需要在最终回答中披露的前提或信息缺口",
    )

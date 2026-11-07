"""足球研究 Critic 使用的结构化审阅与路由决策模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReviewDecision = Literal["pass", "gather_more", "replan"]
IssueCategory = Literal["evidence", "factual", "scope", "plan"]


class ReviewIssue(BaseModel):
    """Critic 发现的一项具体风险，以及下一节点需要执行的动作。"""

    # 严格字段让路由器可以稳定读取 issues，而不是再靠字符串关键词猜测模型意图。
    model_config = ConfigDict(extra="forbid")

    category: IssueCategory = Field(description="问题属于证据、事实、范围或研究计划哪一类")
    detail: str = Field(min_length=5, max_length=240, description="具体发现的风险或缺口")
    required_action: str = Field(min_length=5, max_length=240, description="下一步需要采取的可执行动作")


class ResearchReview(BaseModel):
    """Critic 的受约束输出，用来驱动 LangGraph 的下一条条件边。"""

    # verdict 是唯一的路由依据；其他字段服务于下一轮 Solver、Planner 和最终回答。
    model_config = ConfigDict(extra="forbid")

    verdict: ReviewDecision = Field(description="pass、gather_more 或 replan")
    rationale: str = Field(min_length=5, max_length=300, description="作出该决定的简洁理由")
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=3, description="最多三项最重要的问题")
    final_answer_limitations: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="即使结束也必须向用户披露的局限性",
    )

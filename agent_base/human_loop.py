"""Human-in-the-loop：在关键研究信息不足时暂停 LangGraph 并接收补充。"""

from __future__ import annotations

from typing import Literal

from langgraph.types import interrupt
from pydantic import BaseModel, Field


class ClarificationRequest(BaseModel):
    """描述一次需要用户补充的研究信息。"""

    question: str
    missing_fields: list[str] = Field(min_length=1)
    reason: str


class HumanInputRequired(BaseModel):
    """Graph 暂停后返回给服务层的安全追问信息。"""

    # run_id 由服务层关联 PostgreSQL 任务；payload 不包含内部提示词或 checkpoint 原文。
    question: str
    missing_fields: list[str]
    reason: str


def build_clarification_request(question: str) -> ClarificationRequest | None:
    """判断问题是否指向某场比赛却未给出可核验范围。

    参数：question 是用户原始研究问题。
    实现：只拦截“这场/本场/刚刚”等指代性比赛提问，普通概念战术问题不暂停，避免过度打断。
    """
    deictic_match = any(marker in question for marker in ("这场", "本场", "刚刚", "上一场"))
    tactical_match = any(marker in question for marker in ("战术", "阵型", "压迫", "复盘", "表现"))
    if not (deictic_match and tactical_match):
        return None
    return ClarificationRequest(
        question="请补充要分析的具体比赛：至少提供对阵双方、比赛日期或赛事名称之一。",
        missing_fields=["对阵双方", "比赛日期或赛事名称"],
        reason="静态战术框架无法单独证明某场比赛执行，缺少比赛范围会导致检索到错误材料。",
    )


def request_human_input(request: ClarificationRequest) -> str:
    """触发 LangGraph interrupt，并在恢复后返回用户补充文本。

    参数：request 是需要展示给用户的追问内容。
    实现：interrupt 持久化当前图状态并暂停；恢复时 LangGraph 将用户输入作为该函数返回值交回。
    """
    response = interrupt({"kind": "clarification", **request.model_dump()})
    return str(response).strip()

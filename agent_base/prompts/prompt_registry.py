"""Prompt 元数据注册表，不在此处保存可能不断变化的大段提示词正文。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSpec:
    """描述一个可被评测和回滚的 Prompt 版本。"""

    # name 用作稳定标识；version 与评测数据关联，避免只靠文件名判断线上 Prompt。
    name: str
    version: str
    purpose: str
    owner_role: str


PROMPT_SPECS = (
    PromptSpec("planner", "v1", "将研究问题拆成可验证子问题", "planner"),
    PromptSpec("solver", "v1", "基于证据撰写研究草案", "solver"),
    PromptSpec("critic", "v1", "评估证据与草案并决定下一条路径", "critic"),
    PromptSpec("finalizer", "v1", "输出可解释的最终中文回答", "finalizer"),
)

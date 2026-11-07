"""按结构化研究计划并行收集足球研究证据，而非让 Solver 自由调用工具。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from tool.services.async_basic_data_service import get_competition_overview
from tool.services.async_web_search_service import search_current_football_info
from tool.shared.data_models import build_tool_error
from knowledge_base.retrieval.local_tactical_retriever import search_local_tactical_knowledge
from tool.services.authoritative_tactical_search_service import search_authoritative_tactics


AsyncEvidenceFetcher = Callable[[str], Awaitable[dict[str, Any]]]


async def fetch_local_tactical_knowledge(query: str) -> dict[str, Any]:
    """在线程池中运行本地概念检索，保持 Collector 的异步并发接口一致。"""
    # 当前检索是轻量磁盘读取与关键词评分；统一转入线程池，未来替换向量数据库时无需改调用方。
    return await asyncio.to_thread(search_local_tactical_knowledge, query)


def requested_source_kinds(plan: dict[str, Any]) -> set[str]:
    """从 Planner 的所有子问题中汇总本轮真正需要的资料类别。"""
    # 使用集合去重，让多个子问题都需要网页资料时只发起一次聚合搜索，控制成本。
    return {
        source_kind
        for sub_question in plan.get("sub_questions", [])
        for source_kind in sub_question.get("required_sources", [])
    }


def detect_supported_competition(question: str) -> str | None:
    """从问题中识别当前异步结构化服务可覆盖的赛事代码。"""
    # 只匹配已经接入 football-data.org 概览服务的赛事，避免伪造不支持的结构化查询。
    aliases = {
        "英超": "PL",
        "premier league": "PL",
        "西甲": "PD",
        "la liga": "PD",
        "德甲": "BL1",
        "bundesliga": "BL1",
        "意甲": "SA",
        "serie a": "SA",
        "法甲": "FL1",
        "ligue 1": "FL1",
        "欧冠": "CL",
        "champions league": "CL",
    }
    normalized_question = question.lower()
    return next((code for alias, code in aliases.items() if alias in normalized_question), None)


def build_web_research_query(question: str, plan: dict[str, Any], review: dict[str, Any]) -> str:
    """将研究目标和最多两项子问题合成为一次高信息密度网页检索。"""
    # 搜索请求数量比逐子问题搜索更影响成本，因此优先合并，再由 Solver 在证据中区分子问题。
    sub_questions = [
        item.get("question", "")
        for item in plan.get("sub_questions", [])[:2]
        if item.get("question")
    ]
    repair_actions = [
        item.get("required_action", "")
        for item in review.get("issues", [])[:2]
        if item.get("required_action")
    ]
    query_parts = [question, *sub_questions, *repair_actions]
    return "；".join(query_parts)


def build_tactical_knowledge_query(question: str, plan: dict[str, Any]) -> str:
    """将原问题与计划子问题合并为适合本地战术概念库的检索问题。"""
    # 基础概念库不需要带入 Critic 的修复指令，只需要稳定的战术主题和研究子问题。
    sub_questions = [
        item.get("question", "")
        for item in plan.get("sub_questions", [])[:3]
        if item.get("question")
    ]
    return "；".join([question, *sub_questions])


async def collect_research_evidence(
    question: str,
    plan: dict[str, Any],
    review: dict[str, Any],
    *,
    web_fetcher: AsyncEvidenceFetcher = search_current_football_info,
    basic_fetcher: Callable[[str], Awaitable[dict[str, Any]]] = get_competition_overview,
    tactical_fetcher: AsyncEvidenceFetcher = fetch_local_tactical_knowledge,
    authoritative_tactical_fetcher: AsyncEvidenceFetcher = search_authoritative_tactics,
) -> tuple[list[dict[str, Any]], list[str]]:
    """按计划并行调用当前可用来源，并明确报告尚未接入的资料类型。"""
    # 只对 Planner 明确要求的来源创建任务，使收集行为可解释、可评测且不会无故消耗 API 配额。
    source_kinds = requested_source_kinds(plan)
    tasks: list[tuple[str, Awaitable[dict[str, Any]]]] = []
    warnings: list[str] = []

    if "web_search" in source_kinds:
        query = build_web_research_query(question, plan, review)
        tasks.append(("web_search", web_fetcher(query)))

    if "basic_data" in source_kinds:
        competition_code = detect_supported_competition(question)
        if competition_code:
            tasks.append(("basic_data", basic_fetcher(competition_code)))
        else:
            warnings.append("计划需要基础数据，但当前异步收集器只支持已识别赛事的联赛概览；未执行猜测性查询。")

    if "tactical_rag" in source_kinds:
        tactical_query = build_tactical_knowledge_query(question, plan)
        tasks.append(("tactical_rag", tactical_fetcher(tactical_query)))

    if "authoritative_tactical_web" in source_kinds:
        tactical_query = build_tactical_knowledge_query(question, plan)
        tasks.append(("authoritative_tactical_web", authoritative_tactical_fetcher(tactical_query)))

    if "user_material" in source_kinds:
        warnings.append("计划需要用户材料，但当前会话未提供可读取的材料；Critic 应将其视为证据缺口。")

    if not tasks:
        # 没有实际可调用来源时仍返回统一错误证据，让 Solver 和 Critic 看到明确原因。
        return [
            build_tool_error(
                source="research_evidence_collector",
                error="当前研究计划没有可执行的已接入资料来源。",
                warnings=warnings,
            )
        ], warnings

    results = await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)
    evidence: list[dict[str, Any]] = []
    for (source_kind, _), result in zip(tasks, results, strict=True):
        if isinstance(result, Exception):
            # 单个来源失败不取消其他并行任务；下游 Critic 会依据 warnings 决定是否补资料。
            evidence.append(
                build_tool_error(
                    source=f"research_evidence_collector:{source_kind}",
                    error=result,
                )
            )
            warnings.append(f"{source_kind} 收集失败：{type(result).__name__}。")
        else:
            evidence.append(result)
            warnings.extend(result.get("warnings", []))
    return evidence, warnings

"""对受审核公开战术来源的网页检索适配器。"""

from __future__ import annotations

from typing import Any

from knowledge_base.learning.source_registry import build_authoritative_tactics_query
from tool.clients.async_tavily_search_client import AsyncTavilySearchClient, AsyncTavilySearchError
from tool.shared.data_models import build_tool_error, build_tool_success


async def search_authoritative_tactics(query: str) -> dict[str, Any]:
    """从 FIFA Training Centre 与 Coaches Voice 获取可引用的公开战术资料摘要。"""
    # 只交给 Tavily 检索公开页面摘要，不大规模下载或复制受版权保护的文章全文。
    try:
        async with AsyncTavilySearchClient() as client:
            payload = await client.search(build_authoritative_tactics_query(query), max_results=5, topic="general", ttl_seconds=24 * 60 * 60)
        results = [{"title": item.get("title"), "url": item.get("url"), "content": item.get("content", "")[:1200], "published_date": item.get("published_date")} for item in payload.get("results", [])]
        return build_tool_success(source="authoritative tactical web", data={"results": results}, freshness="historical", confidence="medium", warnings=["公开文章用于解释战术框架；具体比赛事实仍需比赛数据或同期报道核验。"])
    except (AsyncTavilySearchError, ValueError) as error:
        return build_tool_error(source="authoritative tactical web", error=error)

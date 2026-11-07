"""将 Tavily 异步搜索结果转换为足球 Agent 统一证据格式。"""

from __future__ import annotations

from typing import Any

from tool.clients.async_tavily_search_client import AsyncTavilySearchClient, AsyncTavilySearchError
from tool.shared.data_models import build_tool_error, build_tool_success


def source_priority(url: str) -> int:
    """为官方赛事、俱乐部和权威媒体分配更高的展示优先级。"""
    # 这只调整返回顺序，不会删除普通媒体结果，最终仍需 Agent 标注不确定性。
    official_domains = (
        "premierleague.com", "uefa.com", "fifa.com", "thefa.com", "fcbarcelona.com",
        "realmadrid.com", "arsenal.com", "mancity.com", "liverpoolfc.com", "mlssoccer.com",
        "the-afc.com", "csl-china.com",
    )
    trusted_media_domains = ("bbc.com", "reuters.com", "apnews.com", "theathletic.com")
    hostname = url.lower()
    if any(domain in hostname for domain in official_domains):
        return 0
    if any(domain in hostname for domain in trusted_media_domains):
        return 1
    return 2


def compact_search_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """裁剪 Tavily 原始结果，只保留最终回答和引用需要的字段。"""
    # 过长的网页原文不应直接进入 Graph State，以免无意义消耗模型上下文。
    results = [
        {
            "title": item.get("title"),
            "url": item.get("url"),
            "published_date": item.get("published_date"),
            "content": item.get("content"),
            "relevance_score": item.get("score"),
        }
        for item in payload.get("results", [])
    ]
    return sorted(results, key=lambda item: source_priority(item.get("url") or ""))


async def search_current_football_info(
    query: str,
    *,
    max_results: int = 5,
    client: AsyncTavilySearchClient | None = None,
) -> dict[str, Any]:
    """异步搜索实时足球资料，并返回统一的来源化网页证据。"""
    # 未传 Client 时自行创建并关闭；Graph 后续可注入共享 Client 进一步减少连接开销。
    own_client = client is None
    active_client = client or AsyncTavilySearchClient()

    try:
        payload = await active_client.search(query, max_results=max_results)
        results = compact_search_results(payload)
        warnings = ["网页资料可能存在发布时间差，最终结论应优先引用官方来源并说明不确定性。"]
        if not results:
            warnings.append("未找到可用网页结果。")
        return build_tool_success(
            source="Tavily web search",
            freshness="recent",
            confidence="medium",
            data={"query": query, "results": results},
            warnings=warnings,
        )
    except (AsyncTavilySearchError, ValueError) as error:
        # 搜索失败也返回标准结果，让 LangGraph 可继续走清晰的失败回答逻辑。
        return build_tool_error(source="Tavily web search", error=error)
    finally:
        # 仅关闭本函数创建的 Client，注入的共享 Client 仍由外部生命周期管理。
        if own_client:
            await active_client.aclose()

"""Tavily 网页检索 Tool：为免费足球 API 未覆盖的信息提供来源化兜底。"""

import json
import os
from typing import Any

import requests
from langchain_core.tools import tool

from tool.shared.data_models import build_tool_error, build_tool_success
from tool.shared.sqlite_cache import SqliteTtlCache, make_cache_key


class TavilySearchError(Exception):
    """Tavily 配置、网络请求或响应发生错误时使用的异常。"""


cache = SqliteTtlCache()


def tool_result(data: dict[str, Any]) -> str:
    """把检索结果编码为保留中文的统一 JSON 文本。"""
    # Tool 的返回值同时给模型和开发日志使用，因此不转义中文并保留缩进。
    return json.dumps(data, ensure_ascii=False, indent=2)


def source_priority(url: str) -> int:
    """为常见高可信足球来源分配较小的排序值。"""
    # 官方赛事、俱乐部和权威媒体优先；这只是排序，不会删除其他结果。
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


def tavily_search(query: str, max_results: int) -> list[dict[str, Any]]:
    """调用 Tavily Search API，并提取可引用的网页结果。"""
    # Key 只从环境变量读取，避免被写进代码或日志。
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or api_key == "你的_Tavily_Key":
        raise TavilySearchError("尚未配置 TAVILY_API_KEY，无法使用网页检索兜底。")

    # 相同新闻检索短暂复用，既控制 Tavily 消耗，也不会把旧新闻缓存得太久。
    cache_key = make_cache_key("tavily-news", {"query": query, "max_results": max_results})
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        return cached_results["results"]

    response = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "query": query,
            "topic": "news",
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_published_date": True,
        },
        timeout=20,
    )
    # 401、429 等 HTTP 失败会转换为异常，再由 Tool 返回结构化错误。
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", [])

    # 仅把回答所需字段交给模型，避免无意义地占用上下文。
    compact_results = [
        {
            "title": item.get("title"), "url": item.get("url"),
            "published_date": item.get("published_date"), "content": item.get("content"),
            "relevance_score": item.get("score"),
        }
        for item in results
    ]
    sorted_results = sorted(compact_results, key=lambda item: source_priority(item.get("url") or ""))
    # 新闻信息变化快，因此仅缓存五分钟；缓存的是检索结果，不是模型生成的结论。
    cache.set(cache_key, {"results": sorted_results}, ttl_seconds=5 * 60)
    return sorted_results


@tool
def search_web_football_info(query: str, max_results: int = 5) -> str:
    """检索足球新闻、官方公告或免费 API 未覆盖联赛的信息，并返回可引用来源。

    适合中超、日职、MLS、伤停、转会、教练发言和实时事件的补充核验。
    结果是网页材料而非官方结构化数据库；回答必须附带来源 URL 并说明不确定性。
    """
    try:
        # 限制结果数量，避免单次 Tool 调用产生过多上下文和 Tavily 消耗。
        safe_max_results = max(1, min(max_results, 8))
        return tool_result(build_tool_success(
            source="Tavily web search",
            freshness="recent",
            confidence="medium",
            data={
                "query": query,
                "results": tavily_search(query, safe_max_results),
            },
            warnings=["网页检索结果需要在最终回答中附带具体 URL，并可能与官方即时公告存在时间差。"],
        ))
    except Exception as error:
        return tool_result(build_tool_error(source="Tavily web search", error=error))


WEB_SEARCH_TOOLS = [search_web_football_info]

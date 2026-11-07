"""异步 Tavily 客户端与网页证据服务的缓存、重试和格式测试。"""

import asyncio
import sys
import tempfile
from pathlib import Path

import httpx

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 tool 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tool.clients.async_tavily_search_client import AsyncTavilySearchClient
from tool.services.async_web_search_service import search_current_football_info
from tool.shared.sqlite_cache import SqliteTtlCache


async def check_async_web_search() -> None:
    """验证 Tavily 搜索写缓存，且服务层返回官方来源优先的统一结果。"""
    # MockTransport 模拟 Tavily，避免测试使用真实 Key、网络或搜索额度。
    with tempfile.TemporaryDirectory() as directory:
        cache = SqliteTtlCache(Path(directory) / "cache.db")
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """返回两个不同优先级的网页结果，并统计实际网络请求次数。"""
            # Arsenal 官方网站应在服务层排序后排在 BBC 前面。
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"title": "BBC report", "url": "https://www.bbc.com/sport/football", "content": "media", "score": 0.9},
                        {"title": "Club update", "url": "https://www.arsenal.com/news/update", "content": "official", "score": 0.7},
                    ]
                },
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = AsyncTavilySearchClient(
            api_key="test-key",
            cache=cache,
            http_client=http_client,
        )
        first_result = await search_current_football_info("Arsenal injury news", client=client)
        second_result = await search_current_football_info("Arsenal injury news", client=client)

        assert first_result["ok"] is True
        assert first_result["data"]["results"][0]["title"] == "Club update"
        assert first_result["data"] == second_result["data"]
        assert call_count == 1
        await http_client.aclose()


def main() -> None:
    """作为独立脚本运行异步网页搜索测试。"""
    # asyncio.run 建立事件循环并执行测试协程。
    asyncio.run(check_async_web_search())
    print("异步 Tavily 网页搜索服务测试通过")


if __name__ == "__main__":
    main()

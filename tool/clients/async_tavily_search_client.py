"""带缓存、限流与重试能力的 Tavily 异步网页搜索客户端。"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from tool.shared.sqlite_cache import SqliteTtlCache, make_cache_key


class AsyncTavilySearchError(Exception):
    """异步 Tavily 搜索无法继续时使用的业务异常。"""


class AsyncTavilySearchClient:
    """异步调用 Tavily Search API，并负责缓存、超时、重试与并发控制。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        cache: SqliteTtlCache | None = None,
        timeout_seconds: float = 15.0,
        max_attempts: int = 3,
        max_concurrency: int = 2,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """配置异步 Tavily 客户端；测试时可注入自定义 HTTP Client。"""
        # Tavily Key 默认从 .env 获取；显式传参用于测试或未来多租户配置。
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.cache = cache or SqliteTtlCache()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.http_client = http_client or httpx.AsyncClient()
        self._owns_http_client = http_client is None

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0。")
        if max_attempts <= 0:
            raise ValueError("max_attempts 必须大于 0。")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency 必须大于 0。")

    async def __aenter__(self) -> AsyncTavilySearchClient:
        """支持 async with，使调用方可自动关闭本类创建的 HTTP Client。"""
        # 返回自身，让调用方可以写成 async with AsyncTavilySearchClient() as client。
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """退出 async with 时释放本类拥有的网络连接。"""
        # 即使请求中发生异常也会执行，避免连接池长期残留。
        await self.aclose()

    async def aclose(self) -> None:
        """关闭本类自行创建的 HTTP Client。"""
        # 外部注入的 Client 属于调用方，因此不在这里关闭。
        if self._owns_http_client:
            await self.http_client.aclose()

    def _validate_configuration(self) -> None:
        """确认 Tavily Key 已配置，避免发送必然失败的请求。"""
        # 占位 Key 与缺失 Key 都不能用于真实搜索。
        if not self.api_key or self.api_key == "你的_Tavily_Key":
            raise AsyncTavilySearchError("尚未配置 TAVILY_API_KEY，无法使用网页检索。")

    def _retry_delay_seconds(self, attempt: int, response: httpx.Response | None = None) -> float:
        """优先遵循 Retry-After，否则返回指数退避等待时间。"""
        # 供应商主动给出等待时间时优先遵守；默认序列为 1、2、4 秒。
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), 0.0)
                except ValueError:
                    pass
        return float(2 ** (attempt - 1))

    async def search(self, query: str, *, max_results: int = 5, ttl_seconds: int = 5 * 60, topic: str = "news") -> dict[str, Any]:
        """异步搜索网页；命中缓存时直接返回，临时 HTTP 故障时有限重试。"""
        # Tavily 查询词与结果数量共同组成缓存键，防止不同搜索条件错误复用同一份结果。
        self._validate_configuration()
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query 不能为空。")
        safe_max_results = max(1, min(max_results, 8))
        if topic not in {"news", "general"}:
            raise ValueError("topic 只能是 news 或 general。")
        cache_key = make_cache_key(
            "tavily-news",
            {"query": normalized_query, "max_results": safe_max_results, "topic": topic},
        )
        cached_payload = self.cache.get(cache_key)
        if cached_payload is not None:
            return cached_payload

        request_body = {
            "query": normalized_query,
            "topic": topic,
            "search_depth": "basic",
            "max_results": safe_max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_published_date": True,
        }

        for attempt in range(1, self.max_attempts + 1):
            try:
                # 限制同时搜索数量，避免新闻检索在复杂研究中快速消耗额度。
                async with self.semaphore:
                    response = await self.http_client.post(
                        "https://api.tavily.com/search",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=request_body,
                        timeout=self.timeout_seconds,
                    )

                if response.status_code in {401, 403, 404}:
                    raise AsyncTavilySearchError(
                        f"Tavily 返回 HTTP {response.status_code}，请检查 Key、权限或接口地址。"
                    )
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    if attempt == self.max_attempts:
                        raise AsyncTavilySearchError(
                            f"Tavily 暂时不可用（HTTP {response.status_code}）。"
                        )
                    await asyncio.sleep(self._retry_delay_seconds(attempt, response))
                    continue

                response.raise_for_status()
                payload = response.json()
                self.cache.set(cache_key, payload, ttl_seconds)
                return payload

            except AsyncTavilySearchError:
                # 已转换过的业务错误保留原始说明，不再被通用错误覆盖。
                raise
            except httpx.TimeoutException as error:
                if attempt == self.max_attempts:
                    raise AsyncTavilySearchError("Tavily 网页搜索超时。") from error
                await asyncio.sleep(self._retry_delay_seconds(attempt))
            except httpx.RequestError as error:
                if attempt == self.max_attempts:
                    raise AsyncTavilySearchError("连接 Tavily 失败。") from error
                await asyncio.sleep(self._retry_delay_seconds(attempt))
            except httpx.HTTPStatusError as error:
                raise AsyncTavilySearchError(
                    f"Tavily 返回 HTTP {error.response.status_code}。"
                ) from error

        # 防御性分支：循环内的 return 或 raise 已覆盖正常情况。
        raise AsyncTavilySearchError("Tavily 搜索未获得有效响应。")

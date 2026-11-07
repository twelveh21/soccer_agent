"""带缓存、限流和重试能力的 football-data.org 异步 HTTP 客户端。"""

from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any

import httpx

from tool.shared.sqlite_cache import SqliteTtlCache, make_cache_key
from infrastructure.cache.redis_json_cache import RedisJsonCache


class AsyncFootballDataError(Exception):
    """异步 football-data.org 请求无法继续时使用的业务异常。"""


async def await_cache_result(value: Any) -> Any:
    """兼容同步 SQLite 缓存与异步 Redis 缓存的读取、写入结果。

    参数：
    - value：缓存 get/set 返回的普通值或 awaitable 对象。

    实现逻辑：旧 SQLite 缓存立即返回结果；Redis 缓存返回协程，统一 await 后交给调用方。
    """
    return await value if inspect.isawaitable(value) else value


def clean_query_params(params: dict[str, Any]) -> dict[str, Any]:
    """移除值为 None 的参数，避免把未提供的参数发送给外部 API。"""
    # 例如 dateTo=None 表示用户未设置结束日期，不应被编码成 dateTo=None。
    return {key: value for key, value in params.items() if value is not None}


class AsyncFootballDataClient:
    """以异步方式请求 football-data.org，并统一处理缓存、超时和临时故障。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        cache: SqliteTtlCache | RedisJsonCache | None = None,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        max_concurrency: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """配置请求行为；测试时可传入自定义 HTTP Client，生产时自动创建。"""
        # 默认从 .env 读取配置；显式传参则优先使用传入值，便于测试和未来多供应商切换。
        self.base_url = (base_url or os.getenv("FOOTBALL_DATA_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_API_KEY")
        # 正式服务默认使用 Redis；传入 SQLite 缓存可保持现有离线测试和 CLI 场景兼容。
        self.cache = cache or RedisJsonCache()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.semaphore = asyncio.Semaphore(max_concurrency)

        # 外部传入 Client 时由调用方负责关闭；本类自行创建时则在 aclose 中关闭。
        self.http_client = http_client or httpx.AsyncClient()
        self._owns_http_client = http_client is None

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0。")
        if max_attempts <= 0:
            raise ValueError("max_attempts 必须大于 0。")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency 必须大于 0。")

    async def __aenter__(self) -> AsyncFootballDataClient:
        """支持 async with，使调用方在退出代码块时自动释放 HTTP 连接。"""
        # 返回自身，让调用方可以写成 async with AsyncFootballDataClient() as client。
        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """退出 async with 时关闭本类自行创建的 HTTP Client。"""
        # 无论请求成功或抛错都进入这里，确保网络连接不会长期残留。
        await self.aclose()

    async def aclose(self) -> None:
        """关闭本类拥有的 HTTP Client，释放连接池中的网络资源。"""
        # 注入的测试 Client 不由本类关闭，避免影响调用方后续断言或复用。
        if self._owns_http_client:
            await self.http_client.aclose()

    def _validate_configuration(self) -> None:
        """在请求前确认 URL 与 API Key 已配置，避免无意义的网络调用。"""
        # 示例 Key 不能真的请求外部服务，因此与已有同步客户端保持相同防护。
        if not self.base_url:
            raise AsyncFootballDataError("尚未配置 FOOTBALL_DATA_BASE_URL，无法查询足球数据。")
        if not self.api_key or self.api_key == "你的_football_data_Key":
            raise AsyncFootballDataError("尚未配置 FOOTBALL_DATA_API_KEY，无法查询足球数据。")

    def _retry_delay_seconds(self, attempt: int, response: httpx.Response | None = None) -> float:
        """计算下一次重试前的等待时间，优先遵循服务端的 Retry-After 提示。"""
        # 服务端明确要求等待时优先遵守；无提示时使用 1、2、4 秒的指数退避。
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(float(retry_after), 0.0)
                except ValueError:
                    pass
        return float(2 ** (attempt - 1))

    async def _wait_before_retry(
        self,
        attempt: int,
        response: httpx.Response | None = None,
    ) -> None:
        """按重试策略异步等待，不阻塞其他并发请求。"""
        # asyncio.sleep 会把等待时间让给事件循环，不会像 time.sleep 一样阻塞整个程序。
        await asyncio.sleep(self._retry_delay_seconds(attempt, response))

    async def get(
        self,
        endpoint: str,
        *,
        ttl_seconds: int,
        **params: Any,
    ) -> dict[str, Any]:
        """读取缓存或异步请求一个 API Endpoint，并对临时故障进行有限重试。"""
        # 先验证配置，再避免在 API Key 缺失时错误地把本地缓存当作新鲜实时信息。
        self._validate_configuration()
        clean_params = clean_query_params(params)
        normalized_endpoint = endpoint.lstrip("/")
        cache_key = make_cache_key(
            "football-data.org",
            {"endpoint": normalized_endpoint, "params": clean_params},
        )

        # 命中未过期缓存时无需外部请求，直接节省延迟和免费 API 额度。
        cached_payload = await await_cache_result(self.cache.get(cache_key))
        if cached_payload is not None:
            return cached_payload

        for attempt in range(1, self.max_attempts + 1):
            try:
                # Semaphore 只包住真正的网络请求，限制多个任务同时占用供应商 API。
                async with self.semaphore:
                    response = await self.http_client.get(
                        f"{self.base_url}/{normalized_endpoint}",
                        headers={"X-Auth-Token": self.api_key},
                        params=clean_params,
                        timeout=self.timeout_seconds,
                    )

                # 401、403、404 是配置或资源问题，重复请求不会改变结果，因此立即失败。
                if response.status_code in {401, 403, 404}:
                    raise AsyncFootballDataError(
                        f"football-data.org 返回 HTTP {response.status_code}，请检查权限、套餐或请求路径。"
                    )

                # 429 与 5xx 通常是临时限流或服务端故障，允许在最大次数内退避重试。
                if response.status_code == 429 or 500 <= response.status_code <= 599:
                    if attempt == self.max_attempts:
                        raise AsyncFootballDataError(
                            f"football-data.org 暂时不可用（HTTP {response.status_code}）。"
                        )
                    await self._wait_before_retry(attempt, response)
                    continue

                # 其他 4xx 会抛出 HTTPStatusError，并由下面的异常分支转换为业务错误。
                response.raise_for_status()
                payload = response.json()
                await await_cache_result(self.cache.set(cache_key, payload, ttl_seconds))
                return payload

            except AsyncFootballDataError:
                # 本类已经构造过明确错误信息的场景不应再被通用逻辑覆盖。
                raise
            except httpx.TimeoutException as error:
                if attempt == self.max_attempts:
                    raise AsyncFootballDataError("请求 football-data.org 超时。") from error
                await self._wait_before_retry(attempt)
            except httpx.RequestError as error:
                if attempt == self.max_attempts:
                    raise AsyncFootballDataError("连接 football-data.org 失败。") from error
                await self._wait_before_retry(attempt)
            except httpx.HTTPStatusError as error:
                raise AsyncFootballDataError(
                    f"football-data.org 返回 HTTP {error.response.status_code}。"
                ) from error

        # 理论上循环中的 return 或 raise 已覆盖所有分支；保留防御性错误以满足类型与运行安全。
        raise AsyncFootballDataError("football-data.org 请求未获得有效响应。")

"""AsyncFootballDataClient 的缓存和重试行为测试。"""

import asyncio
import sys
import tempfile
from pathlib import Path

import httpx

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 tool 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tool.clients.async_football_data_client import AsyncFootballDataClient
from tool.shared.sqlite_cache import SqliteTtlCache


async def no_wait(*args, **kwargs) -> None:
    """测试用等待函数：跳过真实退避时间，让重试测试快速完成。"""
    # 生产代码会等待 1、2、4 秒；单元测试只验证逻辑，不需要真的等待。
    return None


async def check_cache_and_retry() -> None:
    """验证第一次请求写缓存、第二次命中缓存，以及 429 后可重试成功。"""
    # 用临时 SQLite 文件和 MockTransport 测试，整个测试不会访问真实 API 或消耗额度。
    with tempfile.TemporaryDirectory() as directory:
        cache = SqliteTtlCache(Path(directory) / "cache.db")
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """模拟 API：积分榜立即成功，赛程先限流再成功。"""
            # 计数用于确认缓存命中时不会再次走到网络层。
            nonlocal call_count
            call_count += 1
            if request.url.path.endswith("/matches") and call_count == 2:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"response": "ok", "path": request.url.path})

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = AsyncFootballDataClient(
            base_url="https://example.test/v4",
            api_key="test-key",
            cache=cache,
            max_attempts=2,
            http_client=http_client,
        )
        client._wait_before_retry = no_wait

        first_payload = await client.get("competitions/PL/standings", ttl_seconds=60)
        second_payload = await client.get("competitions/PL/standings", ttl_seconds=60)
        retry_payload = await client.get("teams/57/matches", ttl_seconds=60)

        assert first_payload == second_payload
        assert retry_payload["response"] == "ok"
        assert call_count == 3
        await http_client.aclose()


def main() -> None:
    """作为独立脚本运行异步测试，方便初学阶段直接查看结果。"""
    # asyncio.run 创建事件循环并运行测试协程。
    asyncio.run(check_cache_and_retry())
    print("AsyncFootballDataClient 缓存与重试测试通过")


if __name__ == "__main__":
    main()

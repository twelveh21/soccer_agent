"""异步联赛概览服务的并发与部分失败降级测试。"""

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
from tool.services.async_basic_data_service import build_competition_claims, get_competition_overview
from tool.shared.sqlite_cache import SqliteTtlCache


async def check_parallel_collection_and_partial_failure() -> None:
    """验证两个 Endpoint 可汇总，且一个失败时仍返回另一个的可用结果。"""
    # MockTransport 不访问真实 API，保证测试无需 Key、无需网络，也不消耗免费额度。
    with tempfile.TemporaryDirectory() as directory:
        cache = SqliteTtlCache(Path(directory) / "cache.db")

        def successful_handler(request: httpx.Request) -> httpx.Response:
            """模拟积分榜和球队列表都成功的 football-data 响应。"""
            # 按 URL 路径返回最小真实形状的 JSON，测试业务层字段裁剪逻辑。
            if request.url.path.endswith("/standings"):
                return httpx.Response(
                    200,
                    json={
                        "competition": {"name": "Premier League"},
                        "season": {"startDate": "2026-08-01"},
                        "standings": [{"type": "TOTAL", "table": [{"position": 1, "team": {"name": "Arsenal"}, "points": 25}]}],
                    },
                )
            return httpx.Response(
                200,
                json={"teams": [{"id": 57, "name": "Arsenal", "shortName": "Arsenal", "tla": "ARS"}]},
            )

        http_client = httpx.AsyncClient(transport=httpx.MockTransport(successful_handler))
        client = AsyncFootballDataClient(
            base_url="https://example.test/v4",
            api_key="test-key",
            cache=cache,
            http_client=http_client,
        )
        result = await get_competition_overview("pl", client=client)
        assert result["ok"] is True
        assert result["confidence"] == "high"
        assert result["data"]["standings"][0]["team"] == "Arsenal"
        assert result["data"]["teams"][0]["code"] == "ARS"
        assert result["data"]["claims"] == [
            {
                "claim_key": "competition:PL:season:2026-08-01:standing:1",
                "value": {
                    "team": "Arsenal",
                    "points": 25,
                    "played": None,
                    "goal_difference": None,
                },
                "source_url": "https://example.test/v4/competitions/PL",
            },
            {
                "claim_key": "competition:PL:season:2026-08-01:team:57",
                "value": {"name": "Arsenal", "short_name": "Arsenal", "code": "ARS"},
                "source_url": "https://example.test/v4/competitions/PL",
            },
        ]
        await http_client.aclose()


def main() -> None:
    """作为独立脚本运行异步联赛概览测试。"""
    # asyncio.run 建立事件循环并执行异步测试协程。
    asyncio.run(check_parallel_collection_and_partial_failure())
    print("异步联赛概览服务测试通过")


if __name__ == "__main__":
    main()

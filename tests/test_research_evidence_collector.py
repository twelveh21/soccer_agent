"""研究证据收集器的来源选择、并行汇总和缺口提示测试。"""

import asyncio
import sys
from pathlib import Path
from typing import Any

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.research_evidence_collector import collect_research_evidence


async def fake_web_fetcher(query: str) -> dict[str, Any]:
    """模拟网页证据来源，并保留查询内容供测试验证。"""
    # 不访问网络、不消耗 Tavily 配额，专注验证收集器的编排逻辑。
    return {"ok": True, "source": "fake_web", "data": {"query": query}, "warnings": []}


async def fake_basic_fetcher(code: str) -> dict[str, Any]:
    """模拟结构化联赛资料来源。"""
    # 返回最小统一证据形状即可，收集器不依赖具体足球字段。
    return {"ok": True, "source": "fake_basic", "data": {"code": code}, "warnings": []}


async def fake_tactical_fetcher(query: str) -> dict[str, Any]:
    """模拟本地战术知识库，验证 Collector 会将它作为真实资料源。"""
    # 该假来源让测试只验证编排，不依赖本地知识文件的具体文案。
    return {"ok": True, "source": "fake_tactical", "data": {"query": query}, "warnings": []}


async def check_parallel_collection() -> None:
    """验证计划要求的网页、基础资料和本地战术知识都会并行汇总。"""
    # 英超触发结构化概览；三个来源类别验证 Collector 能编排不同性质的证据。
    plan: dict[str, Any] = {
        "sub_questions": [
            {
                "question": "英超球队如何通过边路制造机会？",
                "required_sources": ["web_search", "basic_data", "tactical_rag"],
            }
        ]
    }
    evidence, warnings = await collect_research_evidence(
        "分析英超球队的边路进攻策略",
        plan,
        {"issues": []},
        web_fetcher=fake_web_fetcher,
        basic_fetcher=fake_basic_fetcher,
        tactical_fetcher=fake_tactical_fetcher,
    )
    assert [item["source"] for item in evidence] == ["fake_web", "fake_basic", "fake_tactical"]
    assert evidence[1]["data"]["code"] == "PL"
    assert "英超球队如何通过边路制造机会？" in evidence[0]["data"]["query"]
    assert "英超球队如何通过边路制造机会？" in evidence[2]["data"]["query"]


def main() -> None:
    """作为独立脚本运行研究证据收集器测试。"""
    # asyncio.run 创建事件循环，以验证真实异步 gather 逻辑而不是只测普通函数。
    asyncio.run(check_parallel_collection())
    print("研究证据收集器测试通过")


if __name__ == "__main__":
    main()

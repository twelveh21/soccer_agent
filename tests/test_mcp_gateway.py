"""验证 MCP 安全网关的白名单、参数限制和外部内容隔离。"""

from __future__ import annotations

import asyncio
import pytest

from tool.mcp_gateway.contracts import McpCallRequest, McpToolPolicy
from tool.mcp_gateway.gateway import McpGateway, McpGatewayDeniedError


def build_gateway() -> McpGateway:
    """构造仅允许 Evidence Collector 查询资料的最小测试网关。

    参数：无。
    实现：策略刻意限制角色、参数、查询长度和 top_k，测试每项边界是否真实生效。
    """
    return McpGateway([
        McpToolPolicy(
            tool_name="trusted_web_search",
            allowed_roles={"evidence_collector"},
            allowed_parameters={"query", "top_k"},
            max_query_length=80,
            max_top_k=3,
        )
    ])


def test_gateway_allows_authorized_call_and_marks_external_content_untrusted() -> None:
    """授权工具可运行，但返回内容必须带不可信外部材料标记。"""
    # Agent 不会因为网关允许调用，就把外部网页/MCP 内容当作系统指令。
    async def fake_tool(arguments: dict[str, object]) -> dict[str, object]:
        """模拟 MCP Server 返回资料，不访问网络。"""
        return {"query": arguments["query"], "text": "外部资料"}

    result = asyncio.run(build_gateway().execute(
        McpCallRequest(caller_role="evidence_collector", tool_name="trusted_web_search", arguments={"query": "阿森纳压迫", "top_k": 2}, run_id="run-1"),
        fake_tool,
    ))
    assert result["untrusted_external_content"] is True
    assert result["source"] == "mcp:trusted_web_search"


def test_gateway_denies_unknown_parameters_before_tool_execution() -> None:
    """未授权参数必须在到达 MCP Server 前被拒绝并记录审计。"""
    # 例如模型试图塞入 shell、url_override 等服务端未设计的参数时，不会透传。
    async def should_not_run(_: dict[str, object]) -> dict[str, object]:
        """若被调用即代表网关失效。"""
        raise AssertionError("被拒绝的 MCP 调用不应执行工具函数。")

    gateway = build_gateway()
    with pytest.raises(McpGatewayDeniedError, match="未授权参数"):
        asyncio.run(gateway.execute(
            McpCallRequest(caller_role="evidence_collector", tool_name="trusted_web_search", arguments={"query": "test", "shell": "rm -rf"}),
            should_not_run,
        ))
    assert gateway.audit_records[-1].decision == "deny"

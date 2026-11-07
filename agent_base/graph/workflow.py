"""为未来拆分保留的 LangGraph 工作流门面。"""

from __future__ import annotations

from typing import Any


def build_workflow(checkpointer: Any) -> Any:
    """返回当前足球 Agent 图，后续可无感替换为拆分后的节点注册实现。"""
    # 延迟导入避免仅使用契约或离线评测时加载模型、数据库和第三方依赖。
    from agent_base.agent import build_soccer_graph

    return build_soccer_graph(checkpointer)

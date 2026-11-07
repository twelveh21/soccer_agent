"""Graphiti 外部图谱适配器的延迟加载入口。"""
from __future__ import annotations
import os
from knowledge_base.temporal_graph.store import InMemoryTemporalGraphStore, TemporalGraphStore

def build_temporal_graph_store() -> TemporalGraphStore:
    """按环境配置选择 Graphiti 图谱或安全的本地替代实现。

    参数：无。
    实现逻辑：默认返回内存实现，保证项目无需 Neo4j 也能运行；只有显式配置 GRAPHITI_ENABLED=true 时，
    才要求后续 Graphiti 服务端连接信息，避免开发环境误发外部请求。
    """
    if os.getenv("GRAPHITI_ENABLED", "false").lower() != "true":
        return InMemoryTemporalGraphStore()
    raise RuntimeError("Graphiti 外部适配器需要在下一次部署配置 GRAPHITI_URL 与图数据库凭证后启用。")

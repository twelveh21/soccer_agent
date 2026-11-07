"""时序图谱存储接口与本地可测试实现。"""
from __future__ import annotations
from datetime import date
from typing import Protocol
from knowledge_base.temporal_graph.contracts import TemporalFact
from knowledge_base.temporal_graph.timeline import resolve_active_facts

class TemporalGraphStore(Protocol):
    """Graphiti/Neo4j 与本地实现共同遵守的时序图谱接口。"""
    def upsert(self, fact: TemporalFact) -> None:
        """写入或更新一条带时间范围的关系事实。"""
    def query_at(self, subject: str, predicate: str, at_date: date) -> list[TemporalFact]:
        """查询某个实体在指定日期有效的关系事实。"""

class InMemoryTemporalGraphStore:
    """用于单元测试和本地演示的轻量时序图谱，不替代生产 Graphiti 存储。"""
    def __init__(self) -> None:
        """初始化空事实列表。

        参数：无。
        实现逻辑：只在进程内保存数据，进程结束即清空，因此不会把演示数据误当正式知识库。
        """
        self._facts: list[TemporalFact] = []

    def upsert(self, fact: TemporalFact) -> None:
        """写入事实；同一来源的完全相同事实会被去重。

        参数：fact 是经过 Pydantic 时间校验的时序关系。
        实现逻辑：按主体、关系、客体、时间范围和来源判断重复；冲突事实保留，交给 timeline 层显式处理。
        """
        if fact not in self._facts:
            self._facts.append(fact)

    def query_at(self, subject: str, predicate: str, at_date: date) -> list[TemporalFact]:
        """读取某日期有效的事实。

        参数：subject/predicate 定位关系；at_date 为比赛日或查询日。
        实现逻辑：复用统一 timeline 查询，保证未来 Graphiti 返回结果和本地演示遵循同一时间规则。
        """
        return resolve_active_facts(self._facts, subject, predicate, at_date)

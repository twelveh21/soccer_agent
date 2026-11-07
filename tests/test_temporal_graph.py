"""验证足球时间事实的查询和冲突检测。"""
from datetime import date
from knowledge_base.temporal_graph.contracts import TemporalFact
from knowledge_base.temporal_graph.timeline import find_conflicts, resolve_active_facts
from knowledge_base.temporal_graph.store import InMemoryTemporalGraphStore

def test_resolve_facts_by_match_date() -> None:
    """同一球员的旧球队关系不应在转会后的比赛日继续生效。

    参数：无。
    实现逻辑：给出前后两段不重叠归属，验证按日期只返回当时有效的球队。
    """
    facts = [TemporalFact(subject="球员A", predicate="plays_for", object="球队甲", valid_from=date(2024, 1, 1), valid_to=date(2024, 6, 30), source_url="https://example.com/a"), TemporalFact(subject="球员A", predicate="plays_for", object="球队乙", valid_from=date(2024, 7, 1), source_url="https://example.com/b")]
    result = resolve_active_facts(facts, "球员A", "plays_for", date(2024, 8, 1))
    assert [fact.object for fact in result] == ["球队乙"]

def test_conflicts_are_not_silently_overwritten() -> None:
    """同一天两个来源声称不同球队时，应报告冲突。

    参数：无。
    实现逻辑：构造重叠有效期，确保系统保留两个来源供 Agent 说明冲突而非随意选择。
    """
    facts = [TemporalFact(subject="球员A", predicate="plays_for", object="球队甲", valid_from=date(2024, 1, 1), source_url="https://example.com/a"), TemporalFact(subject="球员A", predicate="plays_for", object="球队乙", valid_from=date(2024, 1, 1), source_url="https://example.com/b")]
    assert len(find_conflicts(facts, date(2024, 2, 1))) == 1

def test_store_uses_the_same_date_filtering_contract() -> None:
    """图谱存储的查询结果应遵守统一有效期规则。

    参数：无。
    实现逻辑：写入开放有效期事实后按未来日期查询，验证适配层不会丢失 timeline 语义。
    """
    store = InMemoryTemporalGraphStore()
    store.upsert(TemporalFact(subject="球队A", predicate="coached_by", object="教练A", valid_from=date(2025, 1, 1), source_url="https://example.com/coach"))
    assert store.query_at("球队A", "coached_by", date(2025, 3, 1))[0].object == "教练A"

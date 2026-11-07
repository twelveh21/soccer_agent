"""按指定日期查询和校验时序足球事实。"""
from __future__ import annotations
from datetime import date
from knowledge_base.temporal_graph.contracts import TemporalFact

def is_active_on(fact: TemporalFact, at_date: date) -> bool:
    """判断一条关系在给定日期是否有效。

    参数：fact 是待判断时序事实；at_date 是用户问题对应的比赛日或查询日。
    实现逻辑：日期必须不早于 valid_from，且不晚于 valid_to；没有 valid_to 表示关系仍可能持续。
    """
    return fact.valid_from <= at_date and (fact.valid_to is None or at_date <= fact.valid_to)

def resolve_active_facts(facts: list[TemporalFact], subject: str, predicate: str, at_date: date) -> list[TemporalFact]:
    """取得某实体在指定日期有效的同类关系。

    参数：facts 是已收集的时序事实；subject/predicate 定位关系；at_date 是目标日期。
    实现逻辑：先按主体和关系过滤，再按有效期判断，最后按置信度从高到低返回，供 Agent 选择证据。
    """
    return sorted((fact for fact in facts if fact.subject == subject and fact.predicate == predicate and is_active_on(fact, at_date)), key=lambda fact: fact.confidence, reverse=True)

def find_conflicts(facts: list[TemporalFact], at_date: date) -> list[tuple[TemporalFact, TemporalFact]]:
    """发现同一主体、关系在同一天指向不同对象的冲突事实。

    参数：facts 是待检查时序事实；at_date 是需要核验的日期。
    实现逻辑：先取当天有效事实，再两两比较 subject/predicate 相同但 object 不同的记录；冲突不会被静默覆盖。
    """
    active = [fact for fact in facts if is_active_on(fact, at_date)]
    conflicts: list[tuple[TemporalFact, TemporalFact]] = []
    for index, left in enumerate(active):
        for right in active[index + 1:]:
            if left.subject == right.subject and left.predicate == right.predicate and left.object != right.object:
                conflicts.append((left, right))
    return conflicts

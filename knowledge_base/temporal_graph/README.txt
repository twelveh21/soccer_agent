本目录放足球时间知识图谱的领域层。

第一阶段不直接依赖 Neo4j 或 Graphiti：先统一“实体—关系—有效时间—来源”的事实形状，
并提供按某日查询有效事实、识别冲突的纯 Python 逻辑。
后续 Graphiti 适配器会把这些 TemporalFact 写入时间图谱，用于球员转会、伤病、球队归属和教练任期等会变化的事实。

store.py 提供统一的 TemporalGraphStore 接口和无外部依赖的 InMemoryTemporalGraphStore；
graphiti_adapter.py 默认安全降级为本地实现，只有显式启用 GRAPHITI_ENABLED 时才尝试外部 Graphiti 图服务。

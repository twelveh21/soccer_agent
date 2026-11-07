shared：工具层共享基础组件

- data_models.py：统一成功与失败结果格式，包含来源、查询时间、新鲜度、可信度、data 和 warnings。
- sqlite_cache.py：SQLite TTL 缓存，负责生成缓存键、存取 JSON 数据和清理过期缓存。
- evidence_quality.py：统一检查来源优先级、查询时间、新鲜度和 data.claims 中的结构化事实冲突。

这里的代码不包含特定足球业务，多个数据源和服务都可复用。

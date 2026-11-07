tests：自动化测试

测试使用 httpx.MockTransport 模拟第三方 API，因此不会消耗 football-data.org 或 Tavily 的真实额度。

- test_async_football_data_client.py：验证异步客户端的缓存命中和 429 重试。
- test_async_basic_data_service.py：验证联赛概览的并发汇总与统一数据格式。
- test_async_web_search_service.py：验证异步 Tavily 搜索的缓存和官方来源排序。
- test_evidence_quality.py：验证来源优先级和结构化事实冲突检测。
test_research_plan.py：研究 Planner 的 Pydantic 结构化输出契约测试，不调用模型。
test_run_observability.py：SQLite 运行记录、节点耗时和隐私化问题指纹测试。
test_research_review.py：Critic 的 pass/gather_more/replan 结构化决定契约测试。
test_research_loop_routing.py：Critic 决定与最大轮次上限的 LangGraph 条件路由测试。
test_research_evidence_collector.py：研究计划驱动的并行来源收集与能力缺口提示测试。
test_workflow_evals.py：固定问题集的路由回归与运行轨迹契约评测。
test_model_gateway.py：模型角色选择、超时重试参数和客户端缓存测试，不调用真实模型。

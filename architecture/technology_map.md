# Soccer Agent 技术地图

| 能力 | 代码入口 | 当前状态 | 后续实现目标 |
| --- | --- | --- | --- |
| LangGraph 编排 | `agent_base/agent.py` | implemented | 拆分节点注册与运行器 |
| Planner Solver Critic | `agent_base/research_plan.py` 等 | implemented | 增加版本化 Prompt 与真实集评测 |
| 模型网关 | `agent_base/model_gateway.py` | implemented | 记录逐调用 Token 与费用 |
| 实时数据与网页证据 | `tool/` | implemented | MCP 适配器、更多数据源 |
| RAG | `knowledge_base/` | scaffolded | 导入、检索、重排、引用 |
| Memory Note | `memory/contracts.py` | scaffolded | 连接既有记忆服务或独立实现 |
| 安全与 HITL | `agent_base/guardrails/` | scaffolded | 策略执行器与 LangGraph interrupt |
| Redis PostgreSQL | `infrastructure/` | scaffolded | 缓存、限流、生产持久化 |
| 评测 | `evaluation/` 和 `agent_base/evals/` | partially implemented | 真实轨迹与质量评分 |
| 可观测性 | `agent_base/run_observability.py` | partially implemented | OpenTelemetry 或 Langfuse |
| API SSE | `service/` | scaffolded | FastAPI 路由与流式研究事件 |
| 容器化 | `docker/` | scaffolded | Dockerfile、Compose、健康检查 |
| 多模态 | `multimodal/` | scaffolded | 阵型图、战术板、截图分析 |

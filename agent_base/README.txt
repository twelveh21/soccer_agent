agent_base：Agent 编排层

agent.py 是项目的主入口，包含：
- DashScope/Qwen 模型初始化。
- LangGraph State、节点、路由和工作流编译。
- 基础数据、实时信息、深度研究三条路径。
- SQLite Checkpointer 与命令行交互入口。
- research_plan.py 定义 Planner 的 Pydantic 结构化研究计划契约，供后续并行收集、Critic 与评测复用。
- run_observability.py 记录每次工作流的节点轨迹、耗时与失败类型；不保存原始用户问题和模型正文。
- research_review.py 定义 Critic 的结构化决定，使 Graph 可以受控地补充证据或重新规划。
- research_evidence_collector.py 按研究计划并行收集网页和结构化资料，并显式报告未接入来源。
- model_gateway.py 统一角色模型、超时和重试配置，为模型降级、成本统计和多模型实验提供入口。

requirements.txt 记录 Python 依赖；.env.example 提供环境变量模板。
soccer_agent.db 保存同步 LangChain Agent 的角色检查点，不应手动编辑。
异步 LangGraph 的 State 检查点位于 data/soccer_graph.db。

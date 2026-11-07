SoccerAgent 项目总览

这是一个面向实时足球数据与可解释战术研究的 Agent 学习项目。

已经实现：
- LangGraph 三路工作流：基础数据、实时资讯、Planner-Collector-Solver-Critic 研究闭环。
- 异步 football-data.org 与 Tavily 工具：缓存、并发限制、超时、有限重试和证据质量检查。
- 本地战术 RAG V1：结构化资料、切块索引、可解释混合检索、引用与离线检索评测。
- SQLite：Graph 检查点、TTL 工具缓存、运行观测、显式 Memory/Note。
- FastAPI：/health、/v1/research、/v1/research/stream（SSE）以及记忆管理 API。
- Docker：Dockerfile、Compose、健康检查和 data 持久卷。

目录说明：
- agent_base：模型网关、LangGraph 工作流、研究角色、评测与 CLI。
- tool：外部数据客户端、业务服务、LangChain Tools 与共享证据模型。
- knowledge_base：战术资料、入库切块、索引与检索器。
- service：FastAPI、请求响应 Schema 与 SSE。
- memory：显式确认的 SQLite Memory/Note。
- evaluation、tests：检索、路由、循环和工具行为的回归验证。
- data：SQLite 检查点、缓存、运行记录和记忆数据。

本地 API：uvicorn service.app:app --host 127.0.0.1 --port 8000
容器启动：docker compose up --build
CLI 入口：agent_base/agent.py
依赖列表：agent_base/requirements.txt

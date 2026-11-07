服务层

FastAPI 服务已复用 SoccerResearchTeam：GET /health 用于健康检查，POST /v1/research 返回完整回答，POST /v1/research/stream 以 SSE 发送任务开始与最终结果。API 不复制 LangGraph 节点逻辑。

本地启动：uvicorn service.app:app --host 127.0.0.1 --port 8000

后台 Worker 与任务队列

工作分工：
- FastAPI：快速接收请求，写入 background_tasks，投递 Celery 消息后立即返回 HTTP 202。
- Redis：保存 Celery 队列消息和短期任务结果。
- Celery Worker：独立进程，从 Redis 取任务并执行耗时工作。
- PostgreSQL：保存任务的 queued / running / success / failed 状态，作为最终可查询记录。

当前任务：
- demo_echo_task：验证 API、队列、Worker、PostgreSQL 链路。
- ingest_document_task：异步导入 TXT、Markdown、PDF，提取文本并写入 document_chunks。

图片战术板仍走即时视觉分析；文章级 Embedding、向量检索和 reranker 会在高级 RAG 模块接入。

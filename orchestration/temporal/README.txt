Temporal：可恢复长任务编排

使用范围：战术文章批量导入、PDF 解析、RAG 建索引、离线评测、长期战术学习。

不使用范围：当前网页的一问一答、普通赛程查询。这些短任务仍由 FastAPI / LangGraph / Celery 处理。

核心分工：

- Workflow：只编排步骤顺序、超时和重试；它的历史由 Temporal Server 持久化。
- Activity：执行真实 I/O 工作，例如调用 Worker 的资料导入、索引构建或评测函数。
- Worker：轮询任务队列并执行 Workflow/Activity。
- Client：由 FastAPI 或管理脚本发起一个带稳定 workflow_id 的长任务。

安装方式：`pip install -r requirements-temporal.txt`，并配置 `TEMPORAL_ADDRESS`（本地开发一般为 `localhost:7233`）。本项目默认不启用该能力，避免没有 Temporal Server 时影响当前网页。

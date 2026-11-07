# Soccer Agent

面向实时足球信息与可解释战术研究的 Agent 学习项目。它将问题分为结构化足球数据、时效资讯与深度战术研究三条路径，并通过 LangGraph 管理多 Agent 研究闭环。

## 能做什么

- 查询赛程、积分榜、球队与球员等结构化足球信息。
- 检索伤停、转会和新闻等时效资料，并保留来源边界。
- 对战术问题执行 Planner、Collector、Solver、Critic、Finalizer 研究流程。
- 使用本地战术知识库和受约束的公开战术资料源补充概念框架。
- 提供独立对话、文件上传、图片材料观察、Memory/Note 与 FastAPI 服务接口。

## 架构亮点

```text
用户问题
  -> 输入检查与路由
  -> 基础数据 / 实时网页 / 战术研究
  -> 证据核验
  -> 最终回答、来源与局限
```

战术研究路径：`Planner -> Collector -> Solver -> Critic -> Finalizer`。

- Solver 不具备工具权限，只依据 Collector 留在 State 的证据推理。
- Critic 只返回 `pass`、`gather_more`、`replan`，并使用最大轮次限制控制成本。
- SQLite 保存 Graph checkpoint、TTL 缓存、运行轨迹和显式记忆。
- 评测覆盖路由、研究循环、战术检索、引用存在性与局限披露。

## 本地启动

1. 复制 `.env.example` 为 `.env`，填入自己的 API Key。
2. 安装依赖：

```bash
python -m pip install -r agent_base/requirements.txt
```

3. 启动服务：

```bash
python -m uvicorn service.app:app --host 127.0.0.1 --port 8000 --reload
```

4. 浏览器打开 `http://127.0.0.1:8000/`。

## Docker

复制 `.env.example` 为 `.env` 并填入模型 Key 后执行：

```bash
docker compose up --build
```

该命令会默认启动 FastAPI、PostgreSQL、Redis 和 Celery Worker。启动顺序是：数据库/Redis 健康
→ FastAPI 自动执行 `alembic upgrade head` → API 与 Worker 开始工作。

服务启动后访问 `http://localhost:8000/`；数据使用 `soccer_agent_data`、`soccer_agent_postgres`
和 `soccer_agent_redis` 命名卷持久化。可用以下命令查看状态：

```bash
docker compose ps
```

## 验证

```bash
python agent_base/evals/run_offline_evals.py
python evaluation/run_tactical_retrieval_evals.py
python evaluation/run_research_answer_evals.py
```

## CI

每次向 `main` 或 `master` 推送代码、创建 Pull Request 时，GitHub Actions 会自动：

1. 安装运行依赖和 `requirements-dev.txt` 中的测试依赖；
2. 编译主要 Python 模块；
3. 运行 `tests/` 单元测试；
4. 校验 Docker Compose 配置并构建 API、Worker 镜像。

工作流文件位于 `.github/workflows/ci.yml`。CI 不携带真实模型 Key，也不会发起真实模型调用。

## DSPy / GEPA 优化实验

`optimization/` 与在线 Agent 隔离：先用固定题集和文字反馈建立基线，再用 DSPy/GEPA 在明确模型调用预算内优化 Solver 指令。基线不调用模型：

```bash
python scripts/run_optimization_baseline.py
```

真正运行优化实验前才安装可选依赖：

```bash
python -m pip install -r requirements-optimization.txt
```

## 项目边界

该版本适合本地演示和小范围体验。生产公开部署仍需补充账号鉴权、访问限流、HTTPS、密钥托管和多用户数据隔离。

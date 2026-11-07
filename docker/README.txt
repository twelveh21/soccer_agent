容器化部署

Dockerfile 构建非 root 的 Python 运行镜像；docker-compose.yml 会一起启动 FastAPI、PostgreSQL、Redis 和 Celery Worker。

启动：复制 .env.example 为 .env，填写模型 Key，然后在项目根目录运行：
docker compose up --build

启动顺序：PostgreSQL/Redis 健康后 -> FastAPI 执行 alembic upgrade head -> API 对外提供 8000 端口；Worker 同时消费 Redis 队列。
数据持久化：soccer_agent_postgres、soccer_agent_redis、soccer_agent_data 三个 Docker 命名卷。
验证：docker compose ps 显示 healthy；浏览器访问 http://localhost:8000/；GET /health 返回 ok。

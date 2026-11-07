PostgreSQL 数据层（第一阶段骨架）

这里的职责不是让 Agent 思考，而是为服务化提供可靠的数据边界：
- models/：Python ORM 模型，对应未来 PostgreSQL 表。
- session.py：统一管理连接、事务、回滚与关闭。

当前项目仍可完全使用 SQLite 运行；未填写 DATABASE_URL 不会影响既有网页或 Agent。
下一阶段才会加入 Alembic 迁移、Repository、FastAPI Dependency、JWT 用户认证和真实 PostgreSQL 接入。

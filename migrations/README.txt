Alembic 数据库迁移目录

使用步骤（等 PostgreSQL 启动并填写 DATABASE_URL 后执行）：
1. alembic revision --autogenerate -m "create core backend tables"
2. alembic upgrade head

迁移文件是数据库结构的版本历史。不要在线上通过 Base.metadata.create_all() 偷偷改表；
正式结构变化必须新增一个 migration，便于团队成员和部署环境同步升级。

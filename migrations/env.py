"""Alembic 迁移运行环境：把 ORM 模型元数据交给迁移工具比较。"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from infrastructure.database.base import Base
import infrastructure.database.models  # noqa: F401 - 导入模型以注册到 Base.metadata


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic 由命令行独立启动，不经过 FastAPI 的启动逻辑；这里主动读取项目 .env，
# 让迁移命令与应用服务使用同一个 DATABASE_URL。
load_dotenv(".env")
target_metadata = Base.metadata


def database_url() -> str:
    """从环境变量读取 Alembic 可用的迁移地址，避免提交真实密钥。

    返回值：显式指定 psycopg 驱动的 SQLAlchemy 连接串。
    实现逻辑：Render 注入的标准 ``postgresql://`` 地址没有携带驱动名，
    Alembic 会错误尝试未安装的 psycopg2；此处统一转为项目实际安装的
    ``postgresql+psycopg://``，与应用数据库层保持一致。
    """
    import os

    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("运行 Alembic 前必须先配置 DATABASE_URL。")
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接 PostgreSQL 并执行版本迁移。"""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

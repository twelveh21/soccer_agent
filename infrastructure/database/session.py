"""数据库连接与事务边界，不让业务代码到处直接创建连接。"""

from __future__ import annotations

import os
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseNotConfiguredError(RuntimeError):
    """未配置 PostgreSQL 时给出明确提示，不影响当前 SQLite 演示模式。"""


def database_url() -> str:
    """从环境变量读取数据库地址，密钥不写入代码或日志。"""
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise DatabaseNotConfiguredError(
            "未配置 DATABASE_URL。当前网页仍可使用 SQLite；启用后端数据库后再填写 PostgreSQL 地址。"
        )
    return value


@lru_cache(maxsize=1)
def build_engine():
    """创建并缓存应用级数据库 Engine。"""
    # Engine 是连接池管理器，不是一次查询一个连接。缓存它可以避免每次 API 请求
    # 都新建连接池；数据库地址变更后应重启服务，而不是运行中热切换。
    return create_engine(database_url(), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def build_session_factory() -> sessionmaker[Session]:
    """构造并缓存 Session 工厂；一次 HTTP 请求只应使用一个 Session。"""
    # 参数：无。它从缓存的 Engine 派生工厂；真正的 Session 在请求或仓储方法中创建。
    return sessionmaker(bind=build_engine(), autocommit=False, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI Dependency 入口：成功提交，异常回滚，最后关闭连接。"""
    session = build_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

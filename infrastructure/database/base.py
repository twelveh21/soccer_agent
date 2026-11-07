"""所有 PostgreSQL ORM 模型共用的声明基类。"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 将继承此类的 Python 类映射为数据库表。"""

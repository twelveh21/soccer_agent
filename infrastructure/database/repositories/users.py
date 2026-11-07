"""users 表的数据访问：认证业务不在 FastAPI 路由中直接操作 SQLAlchemy。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.database.models.core import UserModel


@dataclass(frozen=True)
class UserSnapshot:
    """给认证层使用的安全用户视图，不暴露 ORM Session。"""

    user_id: str
    email: str
    password_hash: str
    role: str


class UserRepository:
    """集中管理用户创建和查询，隔离 SQLAlchemy 细节。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """保存数据库 Session 工厂。

        参数：
        - session_factory：每次数据库操作创建独立短事务的工厂。

        实现逻辑：Repository 不跨请求持有 Session，避免并发请求共享未提交的数据。
        """
        self._session_factory = session_factory

    def create(self, email: str, password_hash: str, role: str = "user") -> UserSnapshot:
        """创建普通用户并返回安全快照。

        参数：
        - email：规范化后的登录邮箱。
        - password_hash：Argon2 生成的密码哈希，绝不接收明文密码。
        - role：初始角色；公开注册只能使用默认 user。

        实现逻辑：先检查邮箱是否已存在，再在短事务中插入 users 记录并转换成 Snapshot。
        """
        with self._session_factory.begin() as session:
            exists = session.scalar(select(UserModel.id).where(UserModel.email == email))
            if exists:
                raise ValueError("该邮箱已注册。")
            record = UserModel(email=email, password_hash=password_hash, role=role)
            session.add(record)
            session.flush()
            return self._snapshot(record)

    def get_by_email(self, email: str) -> UserSnapshot | None:
        """按邮箱读取用户，用于登录时核验密码。

        参数：
        - email：用户输入并已规范化的邮箱。

        实现逻辑：只读事务中查询唯一邮箱；不存在时返回 None，不暴露 SQLAlchemy 模型。
        """
        with self._session_factory() as session:
            record = session.scalar(select(UserModel).where(UserModel.email == email))
            return self._snapshot(record) if record else None

    def get_by_id(self, user_id: str) -> UserSnapshot | None:
        """按 JWT 中的用户 ID 读取当前用户。

        参数：
        - user_id：JWT subject（sub）字段携带的用户 ID。

        实现逻辑：从 users 主键查询；不存在通常意味着用户已删除或令牌已失效。
        """
        with self._session_factory() as session:
            record = session.get(UserModel, user_id)
            return self._snapshot(record) if record else None

    @staticmethod
    def _snapshot(record: UserModel) -> UserSnapshot:
        """把 ORM 用户对象转换为不可变认证快照。

        参数：
        - record：当前数据库事务中读取到的 UserModel。

        实现逻辑：认证层只依赖普通数据，不依赖可能已关闭的 SQLAlchemy Session。
        """
        return UserSnapshot(
            user_id=record.id,
            email=record.email,
            password_hash=record.password_hash,
            role=record.role,
        )

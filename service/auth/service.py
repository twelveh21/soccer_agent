"""认证用例：注册、登录和当前用户读取。"""

from __future__ import annotations

from dataclasses import dataclass
import os

from infrastructure.database.repositories.users import UserRepository, UserSnapshot
from service.auth.roles import ROLE_ADMIN, ROLE_USER
from service.auth.security import create_access_token, hash_password, verify_password


class InvalidCredentialsError(ValueError):
    """登录邮箱或密码不正确时抛出的统一错误，避免泄漏具体原因。"""


@dataclass(frozen=True)
class AuthResult:
    """注册或登录成功后返回给 API 路由的令牌和基础身份信息。"""

    access_token: str
    user_id: str
    email: str
    role: str


class AuthService:
    """把认证业务规则从 FastAPI 路由中抽离。"""

    def __init__(self, user_repository: UserRepository) -> None:
        """注入用户仓储。

        参数：
        - user_repository：读写 users 表的数据访问对象。

        实现逻辑：服务层依赖 Repository 接口而非 SQLAlchemy，便于测试与替换存储实现。
        """
        self._users = user_repository

    def register(self, email: str, password: str) -> AuthResult:
        """注册普通用户并立刻签发登录令牌。

        参数：
        - email：用户提交的邮箱。
        - password：至少八位的明文密码，仅在本方法中用于生成哈希。

        实现逻辑：规范化邮箱、哈希密码、创建默认 user 角色；本地初始化时，环境变量指定的
        首个管理员邮箱会被授予 admin，公开请求不能自行选择角色。
        """
        normalized_email = email.strip().lower()
        bootstrap_email = os.getenv("SOCCER_AGENT_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        initial_role = ROLE_ADMIN if bootstrap_email and normalized_email == bootstrap_email else ROLE_USER
        user = self._users.create(normalized_email, hash_password(password), role=initial_role)
        return self._result(user)

    def login(self, email: str, password: str) -> AuthResult:
        """核验账号密码并签发新的 JWT。

        参数：
        - email：登录邮箱。
        - password：登录明文密码。

        实现逻辑：查找用户后用 Argon2 验证；无论邮箱不存在还是密码错误，都返回同一安全错误。
        """
        user = self._users.get_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("邮箱或密码不正确。")
        return self._result(user)

    def get_user(self, user_id: str) -> UserSnapshot | None:
        """读取 JWT 指向的当前用户。

        参数：
        - user_id：JWT 的 subject 字段。

        实现逻辑：委托 Repository 按主键读取，供 FastAPI Dependency 做令牌二次校验。
        """
        return self._users.get_by_id(user_id)

    @staticmethod
    def _result(user: UserSnapshot) -> AuthResult:
        """把用户快照转换为认证成功结果。

        参数：
        - user：数据库读取或新创建的安全用户快照。

        实现逻辑：JWT 只携带身份和角色，不携带 password_hash。
        """
        return AuthResult(
            access_token=create_access_token(user.user_id, user.email, user.role),
            user_id=user.user_id,
            email=user.email,
            role=user.role,
        )

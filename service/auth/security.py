"""密码哈希与 JWT 签发/校验，不在路由层处理敏感逻辑。"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash


class TokenValidationError(ValueError):
    """令牌缺失、伪造或过期时抛出的安全错误。"""


# 推荐配置会选择 Argon2；它只保存不可逆哈希，不保存用户原始密码。
password_hasher = PasswordHash.recommended()
DEFAULT_LOCAL_JWT_SECRET = "soccer-agent-local-development-secret-change-before-production"


def hash_password(password: str) -> str:
    """把注册明文密码转换为 Argon2 哈希。

    参数：
    - password：只在注册处理瞬间存在的明文密码。

    实现逻辑：Argon2 会生成带随机盐的不可逆字符串；数据库只保存返回的哈希。
    """
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """验证登录明文密码是否匹配已保存哈希。

    参数：
    - password：登录请求中的明文密码。
    - password_hash：users 表中保存的 Argon2 哈希。

    实现逻辑：由 Argon2 完成安全比较；路由不会自行比较或记录密码。
    """
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: str, email: str, role: str) -> str:
    """为已验证用户签发有过期时间的 JWT 访问令牌。

    参数：
    - user_id：写入 JWT ``sub`` 的稳定用户 ID。
    - email：用于调试和展示的用户邮箱声明。
    - role：当前角色声明，下一步 RBAC 会用到。

    实现逻辑：以 HS256 签名包含身份、角色和过期时间的 JSON；令牌本身不含密码或数据库连接信息。
    """
    expires_minutes = max(5, int(os.getenv("JWT_EXPIRE_MINUTES", "120")))
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(UTC) + timedelta(minutes=expires_minutes),
    }
    secret = os.getenv("JWT_SECRET", DEFAULT_LOCAL_JWT_SECRET)
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """验证 JWT 签名与过期时间，并取回可信声明。

    参数：
    - token：客户端通过 Authorization: Bearer 提交的访问令牌。

    实现逻辑：只有签名正确且未过期才返回 payload；任何 JWT 解析错误统一转换为安全异常。
    """
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET", DEFAULT_LOCAL_JWT_SECRET), algorithms=["HS256"])
    except jwt.PyJWTError as error:
        raise TokenValidationError("登录状态无效或已过期。") from error
    if not isinstance(payload.get("sub"), str):
        raise TokenValidationError("登录令牌缺少用户标识。")
    return payload

"""FastAPI 认证依赖：从请求令牌解析当前用户。"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from infrastructure.database.repositories.users import UserRepository, UserSnapshot
from infrastructure.database.session import build_session_factory
from service.auth.security import TokenValidationError, decode_access_token
from service.auth.service import AuthService


# auto_error=False 让我们能返回统一中文提示，而不是框架默认英文错误。
bearer_scheme = HTTPBearer(auto_error=False)
auth_service = AuthService(UserRepository(build_session_factory()))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserSnapshot:
    """从 Authorization Bearer JWT 获取已登录用户。

    参数：
    - credentials：FastAPI 从请求头解析的 Bearer token；未携带时为 None。

    实现逻辑：先校验 JWT 签名/过期时间，再按 sub 查询 users 表；双重校验避免已删除用户继续访问。
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录。")
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenValidationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    user = auth_service.get_user(payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="当前用户不存在或已被删除。")
    return user

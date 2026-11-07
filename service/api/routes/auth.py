"""注册、登录和当前用户接口。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from infrastructure.database.repositories.users import UserSnapshot
from service.api.schemas import AuthRequest, AuthTokenResponse, CurrentUserResponse
from service.auth.dependencies import auth_service, get_current_user
from service.auth.service import InvalidCredentialsError


router = APIRouter(prefix="/v1/auth", tags=["authentication"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: AuthRequest) -> AuthTokenResponse:
    """注册一个默认 user 角色并返回 JWT。

    参数：
    - request：包含邮箱和至少八位密码的注册请求。

    实现逻辑：AuthService 处理哈希和 users 写入；邮箱已存在时返回 409，不返回任何密码信息。
    """
    try:
        result = await asyncio.to_thread(auth_service.register, request.email, request.password)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return AuthTokenResponse(**result.__dict__)


@router.post("/login", response_model=AuthTokenResponse)
async def login(request: AuthRequest) -> AuthTokenResponse:
    """核验用户密码并签发短期访问令牌。

    参数：
    - request：登录邮箱和密码。

    实现逻辑：密码校验在 AuthService 内部完成；失败时统一返回 401，避免暴露邮箱是否注册。
    """
    try:
        result = await asyncio.to_thread(auth_service.login, request.email, request.password)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    return AuthTokenResponse(**result.__dict__)


@router.get("/me", response_model=CurrentUserResponse)
async def current_user(user: UserSnapshot = Depends(get_current_user)) -> CurrentUserResponse:
    """返回当前 Bearer JWT 对应的基础身份。

    参数：
    - user：认证 Dependency 解出的数据库用户，不由客户端直接传入。

    实现逻辑：只有令牌签名、过期时间和 users 表记录均有效时才返回身份；下一步 RBAC 会复用此依赖。
    """
    return CurrentUserResponse(user_id=user.user_id, email=user.email, role=user.role)

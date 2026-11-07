"""RBAC 角色常量和 FastAPI 权限依赖。"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from infrastructure.database.repositories.users import UserSnapshot
from service.auth.dependencies import get_current_user
from service.auth.roles import VALID_ROLES


def require_roles(*allowed_roles: str) -> Callable[..., object]:
    """创建一个可复用的 FastAPI RBAC 权限检查 Dependency。

    参数：
    - allowed_roles：允许访问某接口的角色，例如 ``editor``、``admin``。

    实现逻辑：先验证开发者配置的角色，再返回内部依赖；请求到达时复用 JWT 验证后的
    当前用户，并以数据库中的当前 role 作为最终授权依据。
    """
    allowed = frozenset(allowed_roles)
    if not allowed or not allowed.issubset(VALID_ROLES):
        raise ValueError("RBAC 配置必须包含至少一个有效角色。")

    async def role_guard(user: UserSnapshot = Depends(get_current_user)) -> UserSnapshot:
        """拒绝没有目标角色的已登录用户。

        参数：
        - user：JWT 验证后从 users 表读取的当前用户。

        实现逻辑：角色以数据库当前值为准；管理员改权后，不必等待旧 JWT 过期。
        """
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前账号没有执行此操作的权限。")
        return user

    return role_guard

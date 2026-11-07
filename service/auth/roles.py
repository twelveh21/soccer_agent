"""认证模块共享的角色定义，不依赖 FastAPI 或数据库。"""

ROLE_USER = "user"
ROLE_EDITOR = "editor"
ROLE_ADMIN = "admin"
VALID_ROLES = frozenset({ROLE_USER, ROLE_EDITOR, ROLE_ADMIN})

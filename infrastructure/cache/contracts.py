"""SQLite 缓存迁移到 Redis 时的通用接口。"""

from __future__ import annotations

from typing import Protocol


class CacheStore(Protocol):
    """工具结果缓存需要支持的最小操作。"""

    def get(self, key: str) -> str | None:
        """按键取回仍在有效期内的值。"""
        # 接口不暴露底层实现，使 SQLite cache 与 Redis adapter 可替换。
        ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """写入带过期时间的缓存值。"""
        # TTL 是实时足球数据的重要语义：不能无限缓存赛果、伤停或积分榜。
        ...

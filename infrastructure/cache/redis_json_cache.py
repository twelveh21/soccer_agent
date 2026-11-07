"""基于 Redis 的 JSON TTL 缓存实现。"""

from __future__ import annotations

import json
from typing import Any

from redis.exceptions import RedisError

from infrastructure.cache.redis_client import get_redis_client


class RedisJsonCache:
    """将 Python 字典序列化为 Redis 字符串，并依靠 Redis TTL 自动过期。"""

    async def get(self, key: str) -> dict[str, Any] | None:
        """读取一个未过期 JSON 缓存。

        参数：
        - key：由数据源名称和请求参数组成的稳定缓存键。

        实现逻辑：Redis 没有该键或连接暂时不可用时返回 None；JSON 损坏时删除键并视为未命中。
        """
        try:
            raw_value = await get_redis_client().get(key)
        except RedisError:
            # 缓存故障不应让实时数据查询完全不可用；调用方会转而请求原始数据源。
            return None
        if raw_value is None:
            return None
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            await self.delete(key)
            return None
        return value if isinstance(value, dict) else None

    async def set(self, key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        """写入带自动过期时间的 JSON 缓存。

        参数：
        - key：缓存键。
        - payload：需要缓存的字典数据。
        - ttl_seconds：有效期秒数，必须大于 0。

        实现逻辑：使用 Redis SET 的 ex 参数，使 Redis 到期后自动删除数据，不需要自己扫描清理。
        """
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds 必须大于 0。")
        try:
            await get_redis_client().set(key, json.dumps(payload, ensure_ascii=False), ex=ttl_seconds)
        except RedisError:
            # 写缓存失败不影响本次已获得的真实数据；下一次请求会再次访问原始数据源。
            return

    async def delete(self, key: str) -> None:
        """删除损坏或不再需要的缓存键。

        参数：
        - key：需要删除的缓存键。

        实现逻辑：删除失败时静默降级，因为缓存清理不能影响用户主请求。
        """
        try:
            await get_redis_client().delete(key)
        except RedisError:
            return

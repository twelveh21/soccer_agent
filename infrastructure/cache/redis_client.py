"""Redis 连接层：为缓存、限流和后台任务提供统一异步客户端。"""

from __future__ import annotations

import os
from functools import lru_cache

from redis.asyncio import Redis


class RedisNotConfiguredError(RuntimeError):
    """没有配置 Redis 地址时抛出，提示开发者启用后端基础服务。"""


def redis_url() -> str:
    """读取 Redis 连接地址。

    参数：无。地址统一从环境变量 REDIS_URL 读取，避免把密码写进 Python 代码。

    实现逻辑：返回去除首尾空白的地址；未配置时抛出清晰异常，而不是连接到未知服务。
    """
    value = os.getenv("REDIS_URL", "").strip()
    if not value:
        raise RedisNotConfiguredError("未配置 REDIS_URL。请启动 Redis 并在 .env 中填写连接地址。")
    return value


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    """创建并缓存应用级异步 Redis 客户端。

    参数：无。连接地址由 redis_url() 获取。

    实现逻辑：Redis 客户端内部维护连接池；应用进程中复用一个客户端，避免每次请求重复建连。
    decode_responses=True 让 get() 直接返回字符串，减少缓存 JSON 编解码时的 bytes 处理。
    """
    return Redis.from_url(
        redis_url(),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


async def ping_redis() -> bool:
    """检查 Redis 是否可用。

    参数：无。使用缓存的 Redis 客户端发出 PING 命令。

    实现逻辑：Redis 返回 PONG 时得到 True；连接失败时抛出异常，由健康检查或调用方决定如何降级。
    """
    return bool(await get_redis_client().ping())


async def close_redis_client() -> None:
    """在 FastAPI 关闭时释放 Redis 连接池。

    参数：无。若当前进程从未使用 Redis，则不会创建新客户端。

    实现逻辑：从 lru_cache 读取已有客户端、异步关闭连接池，再清除缓存，便于测试或服务重启。
    """
    cached_clients = get_redis_client.cache_info().currsize
    if not cached_clients:
        return
    client = get_redis_client()
    await client.aclose()
    get_redis_client.cache_clear()

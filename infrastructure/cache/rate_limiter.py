"""基于 Redis 固定时间窗口的 API 限流器。"""

from __future__ import annotations

from dataclasses import dataclass

from redis.exceptions import RedisError

from infrastructure.cache.redis_client import get_redis_client


@dataclass(frozen=True)
class RateLimitDecision:
    """一次限流判断的结果，供 FastAPI 决定放行或返回 HTTP 429。"""

    allowed: bool
    remaining: int
    retry_after_seconds: int


async def check_fixed_window_limit(
    scope: str,
    subject: str,
    *,
    limit: int,
    window_seconds: int,
) -> RateLimitDecision:
    """检查某个用户或匿名会话在固定窗口内是否超过调用次数。

    参数：
    - scope：限流范围，例如 research 或 upload，防止不同接口共用计数。
    - subject：用户 ID 或匿名 session_id，代表被限制的对象。
    - limit：窗口内最多允许的请求数。
    - window_seconds：统计窗口秒数。

    实现逻辑：Redis INCR 每次请求加一；第一次请求同时设置 EXPIRE；计数超过 limit 时拒绝。
    Redis 不可用时选择“放行”，避免缓存基础设施故障使 Agent 完全不可访问。
    """
    if limit < 1 or window_seconds < 1:
        raise ValueError("limit 和 window_seconds 都必须大于 0。")
    key = f"rate_limit:{scope}:{subject}"
    try:
        client = get_redis_client()
        current_count = await client.incr(key)
        if current_count == 1:
            await client.expire(key, window_seconds)
        ttl = await client.ttl(key)
    except RedisError:
        return RateLimitDecision(allowed=True, remaining=limit, retry_after_seconds=0)

    remaining = max(limit - current_count, 0)
    return RateLimitDecision(
        allowed=current_count <= limit,
        remaining=remaining,
        retry_after_seconds=max(ttl, 0),
    )

"""足球 Agent 各类查询工具共用的数据返回结构。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal


Freshness = Literal["realtime", "recent", "historical", "unknown"]
Confidence = Literal["high", "medium", "low"]


def utc_now_iso() -> str:
    """生成统一的 UTC 查询时间字符串。"""
    # 所有数据源都用 UTC 记录查询时刻，避免服务器和比赛所在地时区混淆。
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_tool_success(
    *,
    source: str,
    data: dict[str, Any],
    source_url: str | None = None,
    event_time: str | None = None,
    freshness: Freshness = "unknown",
    confidence: Confidence = "high",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """把任意成功查询包装成足球 Agent 的统一结果格式。"""
    # data 放业务内容；其余字段专门描述来源、时间和可靠性，供 Agent 后续判断。
    return {
        "ok": True,
        "source": source,
        "source_url": source_url,
        "retrieved_at": utc_now_iso(),
        "event_time": event_time,
        "freshness": freshness,
        "confidence": confidence,
        "data": data,
        "warnings": warnings or [],
    }


def build_tool_error(
    *,
    source: str,
    error: Exception | str,
    data: dict[str, Any] | None = None,
    source_url: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """把失败查询也包装成统一格式，避免 Agent 因字段不一致而中断。"""
    # 错误结果保留与成功结果相同的元数据字段，调用方无需写两套解析逻辑。
    return {
        "ok": False,
        "source": source,
        "source_url": source_url,
        "retrieved_at": utc_now_iso(),
        "event_time": None,
        "freshness": "unknown",
        "confidence": "low",
        "data": data or {},
        "warnings": warnings or [],
        "error": str(error),
    }

"""管理员查询本地 OpenTelemetry Trace 的接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from infrastructure.observability.tracing import read_recent_trace_records
from service.api.schemas import TraceSpanResponse
from service.auth.permissions import require_roles
from service.auth.roles import ROLE_ADMIN


router = APIRouter(
    prefix="/v1/observability",
    tags=["observability"],
    dependencies=[Depends(require_roles(ROLE_ADMIN))],
)


@router.get("/traces", response_model=list[TraceSpanResponse])
async def list_recent_traces(limit: int = Query(default=50, ge=1, le=200)) -> list[TraceSpanResponse]:
    """读取最近结束的 Trace Span，供管理员定位慢请求。

    参数：
    - limit：返回最近多少条 Span，最大 200。

    实现逻辑：调用 observability 基础设施读取已脱敏 JSONL；此接口没有模型调用或数据库写入。
    """
    return [TraceSpanResponse(**record) for record in read_recent_trace_records(limit=limit)]


@router.get("/traces/{trace_id}", response_model=list[TraceSpanResponse])
async def get_trace(trace_id: str) -> list[TraceSpanResponse]:
    """读取某个 Trace ID 下的完整步骤链路。

    参数：
    - trace_id：HTTP 响应头 X-Trace-Id 或日志中取得的 Trace 标识。

    实现逻辑：按 Trace ID 筛出同一请求的多个 Span，前端可据此画耗时瀑布图。
    """
    return [TraceSpanResponse(**record) for record in read_recent_trace_records(limit=200, trace_id=trace_id)]

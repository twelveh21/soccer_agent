"""OpenTelemetry 初始化与本地 Trace 导出。"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Sequence

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult, SpanExporter

from infrastructure.database.session import build_engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRACE_FILE = PROJECT_ROOT / "data" / "observability" / "traces.jsonl"
_configured = False
_write_lock = Lock()


class JsonlSpanExporter(SpanExporter):
    """把完成的 OpenTelemetry Span 写入本地 JSONL，便于学习阶段直接查看。"""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """批量导出已经结束的 Span。

        参数：
        - spans：OpenTelemetry 在一个批次中交给导出器的完成 Span。

        实现逻辑：只提取 Span 名称、Trace ID、耗时、状态和安全属性，逐行写为 JSON；
        不写模型提示词、密码、JWT、上传文件正文或外部网页原文。
        """
        try:
            TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
            lines: list[str] = []
            for span in spans:
                context = span.get_span_context()
                duration_ms = round((span.end_time - span.start_time) / 1_000_000, 2)
                attributes = {
                    key: value
                    for key, value in dict(span.attributes or {}).items()
                    if not any(secret in key.lower() for secret in ("authorization", "password", "token", "cookie"))
                }
                lines.append(
                    json.dumps(
                        {
                            "timestamp": datetime.now(UTC).isoformat(),
                            "trace_id": format(context.trace_id, "032x"),
                            "span_id": format(context.span_id, "016x"),
                            "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                            "name": span.name,
                            "duration_ms": duration_ms,
                            "status": span.status.status_code.name,
                            "attributes": attributes,
                        },
                        ensure_ascii=False,
                    )
                )
            with _write_lock, TRACE_FILE.open("a", encoding="utf-8") as output:
                output.write("\n".join(lines) + ("\n" if lines else ""))
            return SpanExportResult.SUCCESS
        except Exception:
            # 可观测性不能反向导致主业务失败；导出异常仅丢失本批追踪数据。
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """结束导出器。

        参数：无。

        实现逻辑：当前文件写入没有长期连接，因此没有额外释放动作；保留此方法以符合 Exporter 协议。
        """


def configure_telemetry(app: FastAPI) -> None:
    """为 FastAPI 应用接入 OpenTelemetry 自动与手动追踪。

    参数：
    - app：当前 FastAPI 实例，自动插桩会围绕其每个 HTTP 请求创建根 Span。

    实现逻辑：创建带服务标识的 TracerProvider，使用批量处理器写本地 JSONL，然后自动监听
    FastAPI、SQLAlchemy、httpx；重复调用会直接返回，避免开发重载时重复插桩。
    """
    global _configured
    if _configured or os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        return
    provider = TracerProvider(
        resource=Resource.create(
            {
                SERVICE_NAME: "soccer-agent",
                SERVICE_VERSION: "1.0.0",
                "deployment.environment": os.getenv("SOCCER_ENV", "local"),
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(JsonlSpanExporter()))
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if otlp_endpoint:
        # OTLP 是 OpenTelemetry 的标准传输协议；只有显式配置时才向外部平台发送 Span。
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health")
    SQLAlchemyInstrumentor().instrument(engine=build_engine())
    HTTPXClientInstrumentor().instrument()
    _configured = True


def get_tracer():
    """取得足球 Agent 使用的命名 Tracer。

    参数：无。

    实现逻辑：不同模块用同一个仪表名称创建业务 Span，导出后可按名称查看 Agent 研究耗时。
    """
    return trace.get_tracer("soccer_agent.workflow")


def current_trace_id() -> str | None:
    """读取当前请求 Trace ID，供 API 响应头和问题排查使用。

    参数：无。

    实现逻辑：没有活跃 Span 时返回 None；有时格式化为固定长度十六进制字符串，不暴露内部对象。
    """
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


def add_current_span_attributes(**attributes: str) -> None:
    """给当前请求 Span 补充可检索的业务属性。

    参数：
    - attributes：例如 research_run_id、session_kind 等非敏感字符串属性。

    实现逻辑：当前没有有效 Span 时不做任何事；有 Span 时逐项写入，供本地 JSONL 或后续 OTLP 平台筛选。
    """
    span = trace.get_current_span()
    if not span.get_span_context().is_valid:
        return
    for key, value in attributes.items():
        span.set_attribute(key, value)


def read_recent_trace_records(limit: int = 50, trace_id: str | None = None) -> list[dict[str, Any]]:
    """读取本地 JSONL 中最近的安全 Trace 记录，供管理员排查请求。

    参数：
    - limit：最多返回多少条记录，限制在 1 到 200 之间避免一次读出过多日志。
    - trace_id：可选的完整 Trace ID；传入时只返回同一条请求链路的 Span。

    实现逻辑：逐行解析 JSONL，跳过损坏行；按时间倒序筛选并裁剪数量。该函数只读导出器
    已经脱敏后的数据，路由层仍需要 admin RBAC 才能调用。
    """
    if not TRACE_FILE.exists():
        return []
    safe_limit = max(1, min(limit, 200))
    records: list[dict[str, Any]] = []
    for line in reversed(TRACE_FILE.read_text(encoding="utf-8").splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if trace_id and record.get("trace_id") != trace_id:
            continue
        records.append(record)
        if len(records) >= safe_limit:
            break
    return records

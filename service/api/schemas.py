"""未来 FastAPI 路由复用的请求与响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """客户端提交给足球研究服务的任务。"""

    # session_id 可选，便于 CLI、网页端和 API 客户端复用或隔离上下文。
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    stream: bool = True
    attachment_context: str | None = Field(default=None, max_length=8000)


class AuthRequest(BaseModel):
    """注册或登录的最小身份请求。"""

    # 不使用 EmailStr，避免为当前学习项目额外引入 email-validator 依赖；路由仍会规范化大小写和空格。
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class AuthTokenResponse(BaseModel):
    """认证成功后返回的短期 JWT 与可展示身份。"""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str


class CurrentUserResponse(BaseModel):
    """受保护接口返回的当前用户基础信息。"""

    user_id: str
    email: str
    role: str


class TraceSpanResponse(BaseModel):
    """管理员读取的一条脱敏 OpenTelemetry Span。"""

    timestamp: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    duration_ms: float
    status: str
    attributes: dict = Field(default_factory=dict)


class ResearchResponse(BaseModel):
    """非流式请求的最终响应形状。"""

    # limitations 对应数据缺口、证据不完整等边界，不能用静默省略掩盖。
    run_id: str
    status: Literal["success", "needs_input", "error"]
    answer: str
    limitations: list[str] = Field(default_factory=list)


class HumanResumeRequest(BaseModel):
    """用户对 Human-in-the-loop 追问提交的补充信息。"""

    clarification: str = Field(min_length=1, max_length=2_000)


class ResearchRunDetailResponse(BaseModel):
    """查询已持久化研究任务时返回的状态和结果。"""

    # 内部 status 有 running、success、failed；此接口让前端在断线后按 run_id 恢复任务结果。
    run_id: str
    status: Literal["running", "needs_input", "success", "failed"]
    question: str
    route: str | None = None
    answer: str | None = None
    evidence_summary: dict = Field(default_factory=dict)
    error_message: str | None = None


class ConversationMessageResponse(BaseModel):
    """数据库中一条对话消息的 API 返回格式。"""

    message_id: str
    role: Literal["user", "assistant"]
    content: str


class DemoTaskRequest(BaseModel):
    """用于验证后台队列的最小请求模型，下一步会由资料导入请求替换。"""

    message: str = Field(min_length=1, max_length=200)


class BackgroundTaskResponse(BaseModel):
    """后台任务创建或查询时返回的状态。"""

    task_id: str
    task_type: str
    status: Literal["queued", "running", "success", "failed"]
    result: dict = Field(default_factory=dict)
    error_message: str | None = None
    attempt_count: int = 0


class DocumentImportResponse(BaseModel):
    """提交资料导入任务后立即返回的文档与后台任务标识。"""

    document_id: str
    task_id: str
    document_status: Literal["queued", "processing", "ready", "failed"]
    task_status: Literal["queued", "running", "success", "failed"]


class DocumentDetailResponse(BaseModel):
    """查询资料导入进度与切块结果摘要时的返回格式。"""

    document_id: str
    filename: str
    content_type: str
    ingest_status: Literal["queued", "processing", "ready", "failed"]
    chunk_count: int
    metadata: dict = Field(default_factory=dict)

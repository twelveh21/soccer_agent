"""足球 Agent 后端第一版核心领域表。"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database.base import Base


def new_id() -> str:
    """生成不依赖数据库自增主键的 UUID，便于 API 与异步任务提前引用。"""
    return uuid4().hex


class TimestampMixin:
    """给需要审计的表统一提供创建与更新时间。"""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UserModel(TimestampMixin, Base):
    """登录用户；当前只建立数据模型，认证接口将在下一阶段接入。"""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    conversations: Mapped[list["ConversationModel"]] = relationship(back_populates="user")


class ConversationModel(TimestampMixin, Base):
    """一段用户对话；当前用浏览器 session_id 识别，后续可绑定登录用户。"""

    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    # 未登录访问允许 user_id 为空；完成 JWT 后再把匿名会话绑定给对应用户。
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # client_session_id 来自浏览器前端，当前阶段用于把同一浏览器的多次提问归到同一对话。
    client_session_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="新对话", nullable=False)
    user: Mapped[UserModel] = relationship(back_populates="conversations")
    messages: Mapped[list["MessageModel"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class MessageModel(Base):
    """对话消息；内容与角色拆分，后续可在不重跑 Agent 的情况下恢复聊天记录。"""

    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    conversation: Mapped[ConversationModel] = relationship(back_populates="messages")


class ResearchRunModel(TimestampMixin, Base):
    """一次 Agent 研究任务的业务级记录，与 LangGraph 内部 checkpoint 分层保存。"""

    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued", nullable=False)
    route: Mapped[str | None] = mapped_column(String(32))
    answer: Mapped[str | None] = mapped_column(Text)
    evidence_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class DocumentModel(TimestampMixin, Base):
    """用户上传或管理员导入的文章、PDF、图片等资料元数据。"""

    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    ingest_status: Mapped[str] = mapped_column(String(32), index=True, default="pending", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    chunks: Mapped[list["DocumentChunkModel"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunkModel(Base):
    """文档切块元数据；向量、BM25 与 reranker 将在此表基础上逐步接入。"""

    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    document: Mapped[DocumentModel] = relationship(back_populates="chunks")
    __table_args__ = (Index("uq_document_chunk_ordinal", "document_id", "ordinal", unique=True),)


class BackgroundTaskModel(TimestampMixin, Base):
    """后台任务状态：导入、切块、索引、评测等耗时操作都可落到此表。"""

    __tablename__ = "background_tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EvaluationRunModel(TimestampMixin, Base):
    """一次评测或模型对比实验的记录，为后续 DSPy/GEPA 优化提供数据基础。"""

    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued", nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

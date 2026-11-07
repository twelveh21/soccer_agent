"""background_tasks 表的数据访问实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from infrastructure.database.models.core import BackgroundTaskModel


@dataclass(frozen=True)
class BackgroundTaskSnapshot:
    """给 API 返回的后台任务安全快照。"""

    task_id: str
    task_type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any]
    error_message: str | None
    attempt_count: int


class BackgroundTaskRepository:
    """集中处理后台任务的创建、状态转换和结果查询。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """保存创建短事务 Session 的工厂。

        参数：
        - session_factory：由数据库基础设施提供的 SQLAlchemy Session 工厂。

        实现逻辑：API 和 Worker 共享同一个 Repository；两者不共享 Session，只共享统一状态规则。
        """
        self._session_factory = session_factory

    def create(self, task_type: str, payload: dict[str, Any]) -> str:
        """创建 queued 状态的后台任务。

        参数：
        - task_type：任务类别，例如 document_ingestion 或 demo_echo。
        - payload：Worker 执行任务所需的安全输入数据。

        实现逻辑：先写 PostgreSQL，再把 ID 投递到 Redis 队列；这样队列消息可追溯到正式任务记录。
        """
        with self._session_factory.begin() as session:
            record = BackgroundTaskModel(task_type=task_type, status="queued", payload=payload, result={})
            session.add(record)
            session.flush()
            return record.id

    def mark_running(self, task_id: str) -> None:
        """将 Worker 已取走的任务标记为 running。

        参数：
        - task_id：PostgreSQL 中的后台任务 ID。

        实现逻辑：每次真正开始执行都增加 attempt_count，为后续失败重试和审计提供依据。
        """
        with self._session_factory.begin() as session:
            record = self._get_required(session, task_id)
            record.status = "running"
            record.attempt_count += 1
            record.error_message = None

    def mark_success(self, task_id: str, result: dict[str, Any]) -> None:
        """保存 Worker 成功产出的结构化结果。

        参数：
        - task_id：需要更新的后台任务 ID。
        - result：Worker 输出的安全结果摘要。

        实现逻辑：任务完成后将状态设为 success，供 API 查询或 SSE 推送进度。
        """
        with self._session_factory.begin() as session:
            record = self._get_required(session, task_id)
            record.status = "success"
            record.result = result
            record.error_message = None

    def mark_failed(self, task_id: str, error_message: str) -> None:
        """记录不可恢复的任务失败。

        参数：
        - task_id：需要标记失败的后台任务 ID。
        - error_message：经过脱敏后的失败摘要。

        实现逻辑：保留失败状态和有限长度错误，避免把异常堆栈或密钥写入数据库。
        """
        with self._session_factory.begin() as session:
            record = self._get_required(session, task_id)
            record.status = "failed"
            record.error_message = error_message[:500]

    def get(self, task_id: str) -> BackgroundTaskSnapshot | None:
        """按 ID 查询一项后台任务的当前状态。

        参数：
        - task_id：API 返回给前端的后台任务 ID。

        实现逻辑：查到 ORM 记录后转换为 Snapshot，避免上层依赖仍绑定数据库会话的 ORM 对象。
        """
        with self._session_factory() as session:
            record = session.get(BackgroundTaskModel, task_id)
            if record is None:
                return None
            return BackgroundTaskSnapshot(
                task_id=record.id,
                task_type=record.task_type,
                status=record.status,
                payload=record.payload,
                result=record.result,
                error_message=record.error_message,
                attempt_count=record.attempt_count,
            )

    @staticmethod
    def _get_required(session: Session, task_id: str) -> BackgroundTaskModel:
        """读取必须存在的任务，集中处理记录不存在的错误。

        参数：
        - session：当前数据库事务的 Session。
        - task_id：目标后台任务 ID。

        实现逻辑：找不到记录时抛出 LookupError，避免 Worker 静默成功却没有更新任何任务。
        """
        record = session.get(BackgroundTaskModel, task_id)
        if record is None:
            raise LookupError(f"后台任务不存在：{task_id}")
        return record

"""research_runs 表的数据访问实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from infrastructure.database.models.core import ResearchRunModel


@dataclass(frozen=True)
class ResearchRunSnapshot:
    """从数据库返回给 API 的安全任务视图，不把 ORM 对象直接暴露给上层。"""

    # 每个字段都对应 research_runs 中需要给接口或监控读取的业务数据。
    run_id: str
    status: str
    question: str
    route: str | None
    answer: str | None
    evidence_summary: dict[str, Any]
    error_message: str | None


class ResearchRunRepository:
    """封装研究任务的创建、完成、失败和查询操作。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """保存创建数据库 Session 的工厂。

        参数：
        - session_factory：由 infrastructure.database.session 提供的 Session 创建器。

        实现逻辑：仓储不持有长期 Session；每个方法各自开启短事务，避免请求之间共享
        未提交数据或数据库连接。
        """
        self._session_factory = session_factory

    def create(self, question: str, conversation_id: str | None = None) -> str:
        """创建一条正在运行的研究任务，并返回数据库任务 ID。

        参数：
        - question：用户提交的原始研究问题。
        - conversation_id：未来登录后关联数据库对话；当前未接入时允许为空。

        实现逻辑：创建 status='running' 的记录，flush 让数据库生成 ID，再由事务自动提交。
        """
        with self._session_factory.begin() as session:
            record = ResearchRunModel(
                question=question,
                conversation_id=conversation_id,
                status="running",
                evidence_summary={},
            )
            session.add(record)
            session.flush()
            return record.id

    def mark_success(
        self,
        run_id: str,
        answer: str,
        route: str | None,
        evidence_summary: dict[str, Any] | None = None,
    ) -> None:
        """把已完成的 Agent 回答写回对应研究任务。

        参数：
        - run_id：create 返回的数据库任务 ID。
        - answer：最终给用户展示的回答文本。
        - route：本次走过的 Agent 路由，例如 research 或 basic_data。
        - evidence_summary：可审计的安全摘要，不保存密钥和完整内部提示词。

        实现逻辑：查询目标记录，更新状态和结果；找不到任务时抛出异常，避免静默写错。
        """
        with self._session_factory.begin() as session:
            record = self._get_required(session, run_id)
            record.status = "success"
            record.answer = answer
            record.route = route
            record.evidence_summary = evidence_summary or {}
            record.error_message = None

    def mark_failed(self, run_id: str, error_message: str) -> None:
        """记录任务失败状态，供前端查询和后续排障。

        参数：
        - run_id：需要标记失败的数据库任务 ID。
        - error_message：经过上层脱敏后的错误摘要，最长保存 500 个字符。

        实现逻辑：只存安全摘要，不直接持久化异常堆栈、密钥或用户上传文件内容。
        """
        with self._session_factory.begin() as session:
            record = self._get_required(session, run_id)
            record.status = "failed"
            record.error_message = error_message[:500]

    def mark_waiting_input(self, run_id: str, prompt: str, evidence_summary: dict[str, Any]) -> None:
        """把研究任务标记为等待用户补充，保留安全追问摘要。

        参数：run_id 是任务 ID；prompt 是展示给用户的追问；evidence_summary 是不含敏感文本的暂停元数据。
        实现：任务不视为失败，后续 resume 接口可继续更新同一条记录为 success。
        """
        with self._session_factory.begin() as session:
            record = self._get_required(session, run_id)
            record.status = "needs_input"
            record.answer = prompt
            record.evidence_summary = evidence_summary
            record.error_message = None

    def get(self, run_id: str) -> ResearchRunSnapshot | None:
        """按任务 ID 查询研究任务的可返回视图。

        参数：
        - run_id：客户端或前端保存的研究任务 ID。

        实现逻辑：查到时将 ORM 模型转换为不可变 Snapshot；查不到时返回 None，交给 API 返回 404。
        """
        with self._session_factory() as session:
            record = session.get(ResearchRunModel, run_id)
            return self._snapshot(record) if record else None

    @staticmethod
    def _get_required(session: Session, run_id: str) -> ResearchRunModel:
        """读取必须存在的任务记录。

        参数：
        - session：当前短事务使用的 SQLAlchemy Session。
        - run_id：目标任务 ID。

        实现逻辑：集中处理“记录不存在”这一错误，避免每个写入方法重复判断。
        """
        record = session.get(ResearchRunModel, run_id)
        if record is None:
            raise LookupError(f"研究任务不存在：{run_id}")
        return record

    @staticmethod
    def _snapshot(record: ResearchRunModel) -> ResearchRunSnapshot:
        """把 ORM 记录转换为 API 可安全读取的数据快照。

        参数：
        - record：从 PostgreSQL 读取出的 ResearchRunModel。

        实现逻辑：只复制产品需要的字段，使 API 层不依赖 ORM 内部状态和数据库连接。
        """
        return ResearchRunSnapshot(
            run_id=record.id,
            status=record.status,
            question=record.question,
            route=record.route,
            answer=record.answer,
            evidence_summary=record.evidence_summary,
            error_message=record.error_message,
        )

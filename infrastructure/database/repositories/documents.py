"""documents 与 document_chunks 表的数据访问实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.database.models.core import DocumentChunkModel, DocumentModel


@dataclass(frozen=True)
class DocumentSnapshot:
    """供 API 返回的文档导入状态快照。"""

    document_id: str
    filename: str
    content_type: str
    ingest_status: str
    chunk_count: int
    metadata_json: dict[str, Any]


class DocumentRepository:
    """集中处理资料文档、导入状态与文本切块的数据库写入。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """保存数据库 Session 工厂。

        参数：
        - session_factory：创建短事务 SQLAlchemy Session 的工厂。

        实现逻辑：FastAPI 负责创建文档记录，Worker 负责更新导入状态和切块；两者共享本仓储。
        """
        self._session_factory = session_factory

    def create(self, filename: str, content_type: str, storage_key: str, owner_id: str | None = None) -> str:
        """创建等待 Worker 导入的文档记录。

        参数：
        - filename：用户原始文件名，仅用于展示。
        - content_type：文件 MIME 类型，例如 application/pdf。
        - storage_key：相对 data 目录的存储路径，避免保存机器相关的绝对路径。
        - owner_id：提交资料的登录用户 ID；Worker 不替用户身份做写入。

        实现逻辑：初始状态为 queued；文件正文不写 PostgreSQL，数据库只保存元数据和后续切块。
        """
        with self._session_factory.begin() as session:
            document = DocumentModel(
                filename=filename[:512],
                content_type=content_type,
                storage_key=storage_key,
                owner_id=owner_id,
                ingest_status="queued",
                metadata_json={},
            )
            session.add(document)
            session.flush()
            return document.id

    def mark_processing(self, document_id: str) -> None:
        """将 Worker 已开始处理的文档标记为 processing。

        参数：
        - document_id：目标 documents 表记录 ID。

        实现逻辑：状态单独写入，便于前端在长导入期间显示“正在解析”。
        """
        with self._session_factory.begin() as session:
            self._get_required(session, document_id).ingest_status = "processing"

    def replace_chunks_and_mark_ready(
        self,
        document_id: str,
        chunks: list[str],
        metadata: dict[str, Any],
    ) -> None:
        """替换文档旧切块并将文档标记为 ready。

        参数：
        - document_id：目标文档 ID。
        - chunks：按顺序切好的文本片段。
        - metadata：字符数、切块数等安全导入摘要。

        实现逻辑：先删除旧切块，再批量插入新切块，最后同一事务更新状态；避免半更新数据。
        """
        with self._session_factory.begin() as session:
            document = self._get_required(session, document_id)
            session.execute(delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id))
            session.add_all(
                [
                    DocumentChunkModel(document_id=document_id, ordinal=index, text=chunk, metadata_json={})
                    for index, chunk in enumerate(chunks)
                ]
            )
            document.ingest_status = "ready"
            document.metadata_json = metadata

    def mark_failed(self, document_id: str, message: str) -> None:
        """标记文档导入失败，并保存有限长度错误摘要。

        参数：
        - document_id：目标文档 ID。
        - message：安全错误摘要，不应包含完整堆栈或密钥。

        实现逻辑：把失败原因存入 metadata_json，后续可由 API 展示给用户。
        """
        with self._session_factory.begin() as session:
            document = self._get_required(session, document_id)
            document.ingest_status = "failed"
            document.metadata_json = {"error": message[:500]}

    def get(self, document_id: str) -> DocumentSnapshot | None:
        """读取一篇文档当前的导入状态与切块数量。

        参数：
        - document_id：需要查询的文档 ID。

        实现逻辑：文档不存在返回 None；存在时读取 relationship 的切块数量并转成独立快照。
        """
        with self._session_factory() as session:
            document = session.get(DocumentModel, document_id)
            if document is None:
                return None
            return DocumentSnapshot(
                document_id=document.id,
                filename=document.filename,
                content_type=document.content_type,
                ingest_status=document.ingest_status,
                chunk_count=len(document.chunks),
                metadata_json=document.metadata_json,
            )

    @staticmethod
    def _get_required(session: Session, document_id: str) -> DocumentModel:
        """获取必须存在的文档。

        参数：
        - session：当前数据库事务。
        - document_id：目标文档 ID。

        实现逻辑：集中处理“文档不存在”，让各状态更新方法保持简洁。
        """
        document = session.get(DocumentModel, document_id)
        if document is None:
            raise LookupError(f"资料文档不存在：{document_id}")
        return document

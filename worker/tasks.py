"""Celery Worker 实际执行的后台任务。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from worker.celery_app import celery_app
from infrastructure.database.repositories.background_tasks import BackgroundTaskRepository
from infrastructure.database.repositories.documents import DocumentRepository
from infrastructure.database.session import build_session_factory
from knowledge_base.ingestion.document_text import split_document_text
from multimodal.vision_service import TEXT_TYPES, extract_text_content


task_repository = BackgroundTaskRepository(build_session_factory())
document_repository = DocumentRepository(build_session_factory())
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@celery_app.task(name="soccer_agent.demo_echo_task")
def demo_echo_task(database_task_id: str, message: str) -> dict[str, Any]:
    """执行一个最小后台任务，验证 API、Redis、Worker 和 PostgreSQL 的完整链路。

    参数：
    - database_task_id：background_tasks 表中的任务 ID。
    - message：由 API 传入的演示文本；未来会替换为文章地址、文件 ID 等真实任务参数。

    实现逻辑：Worker 取到 Redis 消息后标记任务 running，生成结构化结果，最后更新为 success。
    若执行异常则写入 failed 后重新抛出，让 Celery 记录失败。
    """
    task_repository.mark_running(database_task_id)
    try:
        result = {
            "echo": message[:200],
            "executed_by": "celery-worker",
            "completed_at": datetime.now(UTC).isoformat(),
        }
        task_repository.mark_success(database_task_id, result)
        return result
    except Exception as error:
        task_repository.mark_failed(database_task_id, "后台 Worker 执行失败。")
        raise error


@celery_app.task(name="soccer_agent.ingest_document_task")
def ingest_document_task(database_task_id: str, document_id: str) -> dict[str, Any]:
    """在后台解析一份文本资料、切块并写入 PostgreSQL。

    参数：
    - database_task_id：background_tasks 表中的任务 ID。
    - document_id：documents 表中等待导入的资料 ID。

    实现逻辑：Worker 读取相对存储路径，提取 TXT/Markdown/PDF 正文，切分为文本块，
    再在同一资料记录下写入 document_chunks；任何异常都会同时标记文档和任务失败。
    """
    task_repository.mark_running(database_task_id)
    document = document_repository.get(document_id)
    if document is None:
        task_repository.mark_failed(database_task_id, "待导入文档不存在。")
        raise LookupError(f"待导入文档不存在：{document_id}")

    try:
        # storage_key 由 API 写为 data 目录下的相对路径，Docker Worker 与本机服务都可解析。
        from infrastructure.database.models.core import DocumentModel
        from infrastructure.database.session import build_session_factory

        with build_session_factory()() as session:
            model = session.get(DocumentModel, document_id)
            if model is None or not model.storage_key:
                raise FileNotFoundError("文档没有可读取的存储路径。")
            content_type = model.content_type
            storage_path = PROJECT_ROOT / "data" / model.storage_key

        if content_type not in TEXT_TYPES:
            raise ValueError("后台资料导入目前只支持 TXT、Markdown 和 PDF。")
        document_repository.mark_processing(document_id)
        raw_content = storage_path.read_bytes()
        extracted_text = extract_text_content(raw_content, content_type)
        chunks = split_document_text(extracted_text)
        if not chunks:
            raise ValueError("资料中没有可用于战术检索的文本内容。")
        metadata = {"character_count": len(extracted_text), "chunk_count": len(chunks), "imported_by": "celery-worker"}
        document_repository.replace_chunks_and_mark_ready(document_id, chunks, metadata)
        result = {"document_id": document_id, **metadata}
        task_repository.mark_success(database_task_id, result)
        return result
    except Exception:
        document_repository.mark_failed(document_id, "资料解析或切块失败。")
        task_repository.mark_failed(database_task_id, "资料导入任务失败。")
        raise

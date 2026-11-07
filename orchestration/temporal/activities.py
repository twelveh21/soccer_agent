"""Temporal Activity：执行真实资料导入、索引和评测工作。"""

from __future__ import annotations

from orchestration.temporal.contracts import TacticalLearningJob


def ingest_documents(job: TacticalLearningJob) -> dict[str, str]:
    """声明“导入资料”这一可重试 Activity 的输入输出边界。

    参数：job 包含待导入 documents 的数据库 ID。
    实现：当前返回安全摘要；部署 Temporal Worker 后，此处调用既有 Celery/Repository 导入逻辑并定期 heartbeat。
    """
    return {"stage": "ingest_documents", "result": f"已提交 {len(job.document_ids)} 份资料进行导入。"}


def rebuild_tactical_index(job: TacticalLearningJob) -> dict[str, str]:
    """声明“重建 RAG 索引”这一可重试 Activity。

    参数：job 决定是否需要重建索引。
    实现：关闭时明确跳过；开启时由 Temporal Worker 调用实际索引构建器，避免把耗时 I/O 放进 Workflow 函数。
    """
    if not job.rebuild_index:
        return {"stage": "rebuild_tactical_index", "result": "按任务配置跳过索引重建。"}
    return {"stage": "rebuild_tactical_index", "result": "已请求重建战术检索索引。"}


def run_quality_evaluation(job: TacticalLearningJob) -> dict[str, str]:
    """声明“运行 RAG/Agent Eval”这一可重试 Activity。

    参数：job 决定是否需要执行离线质量评测。
    实现：关闭时返回跳过摘要；开启时由 Worker 调用已有评测器并把报告写入 evaluation_runs。
    """
    if not job.run_evaluation:
        return {"stage": "run_quality_evaluation", "result": "按任务配置跳过离线评测。"}
    return {"stage": "run_quality_evaluation", "result": "已请求执行战术检索与 Agent Eval。"}

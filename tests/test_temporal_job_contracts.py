"""验证 Temporal 长任务输入和阶段 Activity 的离线契约。"""

from __future__ import annotations

from orchestration.temporal.activities import rebuild_tactical_index, run_quality_evaluation
from orchestration.temporal.contracts import TacticalLearningJob


def test_temporal_job_keeps_large_content_outside_workflow_input() -> None:
    """长任务只传文档 ID，不传 PDF 正文，避免撑大 Temporal 持久化历史。"""
    # 这也是生产环境常用的 claim-check 思路：大文件放存储，工作流只传引用。
    job = TacticalLearningJob(job_id="learning-1", document_ids=["doc-1", "doc-2"])
    assert job.document_ids == ["doc-1", "doc-2"]
    assert "content" not in job.model_dump()


def test_temporal_activities_honor_optional_stages() -> None:
    """关闭索引或评测时，Activity 应返回明确跳过摘要。"""
    # 任务配置可控制耗时阶段，避免每次小资料更新都执行完整昂贵流程。
    job = TacticalLearningJob(job_id="learning-2", document_ids=["doc-1"], rebuild_index=False, run_evaluation=False)
    assert "跳过" in rebuild_tactical_index(job)["result"]
    assert "跳过" in run_quality_evaluation(job)["result"]

"""Temporal Workflow：编排足球资料学习的长任务阶段。"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

from orchestration.temporal.contracts import TacticalLearningJob, TemporalJobResult


@workflow.defn
class TacticalLearningWorkflow:
    """以持久化历史编排导入、索引和评测，允许失败后按步骤恢复。"""

    @workflow.run
    async def run(self, job: TacticalLearningJob) -> TemporalJobResult:
        """顺序执行长任务 Activity，并返回阶段摘要。

        参数：job 是可序列化的资料学习任务。
        实现：Workflow 只协调 Activity；每个 Activity 有独立超时和重试边界，服务重启后 Temporal 根据历史继续而不是从头开始。
        """
        stages = []
        stages.append(
            await workflow.execute_activity(
                "ingest_documents",
                job,
                start_to_close_timeout=timedelta(minutes=20),
            )
        )
        stages.append(
            await workflow.execute_activity(
                "rebuild_tactical_index",
                job,
                start_to_close_timeout=timedelta(minutes=30),
            )
        )
        stages.append(
            await workflow.execute_activity(
                "run_quality_evaluation",
                job,
                start_to_close_timeout=timedelta(minutes=20),
            )
        )
        return TemporalJobResult(job_id=job.job_id, status="success", stages=stages)

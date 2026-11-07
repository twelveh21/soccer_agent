"""启动 Temporal Worker，执行足球资料学习 Workflow 和 Activities。"""

from __future__ import annotations

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from orchestration.temporal.activities import ingest_documents, rebuild_tactical_index, run_quality_evaluation
from orchestration.temporal.workflow import TacticalLearningWorkflow


async def run_worker() -> None:
    """连接 Temporal Server 并持续轮询足球学习任务队列。

    参数：无；连接地址和队列名从环境变量读取。
    实现：注册 Workflow 类和 Activity 函数；Temporal Server 分发任务，Worker 负责真正执行。
    """
    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    worker = Worker(
        client,
        task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "soccer-tactical-learning"),
        workflows=[TacticalLearningWorkflow],
        activities=[ingest_documents, rebuild_tactical_index, run_quality_evaluation],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())

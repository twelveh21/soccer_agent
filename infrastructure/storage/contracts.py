"""SQLite 到 PostgreSQL 演进时保持稳定的仓储契约。"""

from __future__ import annotations

from typing import Protocol


class RunRepository(Protocol):
    """运行元数据仓储需要提供的最小能力。"""

    def get_run_summary(self, run_id: str) -> dict[str, object] | None:
        """读取一次运行的安全摘要。"""
        # RunRecorder 已满足这个读取形状；未来 PostgreSQL 实现不应改变 API 层调用方式。
        ...

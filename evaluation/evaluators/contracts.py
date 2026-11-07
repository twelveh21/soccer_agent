"""统一的可解释评测结果模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """单个评测器的输出，既可用于 CI 也可写入实验报告。"""

    # score 留在 0 到 1；reason 说明失分原因，避免只得到一个无法行动的总分。
    evaluator_name: str
    case_id: str
    status: Literal["pass", "fail", "skip"]
    score: float = Field(ge=0, le=1)
    reason: str
    metrics: dict[str, float] = Field(default_factory=dict)

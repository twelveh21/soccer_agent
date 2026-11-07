"""时间知识图谱的稳定领域模型。"""
from __future__ import annotations
from datetime import date
from pydantic import BaseModel, Field, model_validator

class TemporalFact(BaseModel):
    """一条随时间变化的足球关系事实。"""
    subject: str = Field(min_length=1, description="关系主体，例如球员或球队")
    predicate: str = Field(min_length=1, description="关系类型，例如 plays_for、injured、coached_by")
    object: str = Field(min_length=1, description="关系客体，例如球队、伤病状态或教练")
    valid_from: date = Field(description="该事实开始成立的日期")
    valid_to: date | None = Field(default=None, description="事实结束日期；未知或仍有效时为空")
    source_url: str = Field(min_length=1, description="该事实的可回溯来源")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_time_range(self) -> "TemporalFact":
        """保证结束时间不早于开始时间。

        参数：self 是 Pydantic 已完成字段解析的事实对象。
        实现逻辑：只允许开放区间或从早到晚的闭区间，避免时间查询得到自相矛盾的关系。
        """
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to 不能早于 valid_from。")
        return self

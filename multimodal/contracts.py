"""多模态输入和视觉证据的最小契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VisualInput(BaseModel):
    """用户授权上传、并明确用途的视觉材料。"""

    # storage_ref 只指向受控对象存储或临时文件标识，不直接把二进制图片写入 Graph State。
    input_id: str
    kind: Literal["formation_board", "match_screenshot", "tactical_diagram"]
    storage_ref: str
    user_claimed_context: str | None = None


class VisualEvidence(BaseModel):
    """视觉模型抽取出的可审阅观察，不把推测伪装成事实。"""

    # confidence 是模型观察置信度；observations 必须可被最终回答标注为“图中可见”。
    input_id: str
    observations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
    formation: str | None = None
    visible_player_count: int | None = Field(default=None, ge=0, le=30)
    directional_arrows: list[str] = Field(default_factory=list)
    pitch_zones: list[str] = Field(default_factory=list)
    visible_labels: list[str] = Field(default_factory=list)


class StructuredVisualObservation(BaseModel):
    """视觉模型可输出的受限结构化观察字段。"""

    # 所有字段只描述画面可见内容；formation 为空代表图中信息不足，不能由模型猜测补全。
    observations: list[str] = Field(default_factory=list, max_length=6)
    formation: str | None = None
    visible_player_count: int | None = Field(default=None, ge=0, le=30)
    directional_arrows: list[str] = Field(default_factory=list, max_length=8)
    pitch_zones: list[str] = Field(default_factory=list, max_length=8)
    visible_labels: list[str] = Field(default_factory=list, max_length=12)
    confidence: float = Field(default=0.55, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list, max_length=6)

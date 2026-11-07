"""验证多模态上传的文件类型校验与用户材料证据边界。"""

from __future__ import annotations

import pytest

from multimodal.contracts import VisualEvidence
from multimodal.evidence_context import build_user_material_context
from multimodal.vision_service import UploadAnalysisError, validate_upload_content


def test_visual_upload_rejects_a_spoofed_png_type() -> None:
    """伪装成 PNG 的普通文本必须在视觉模型调用前被拒绝。"""
    # MIME 类型由浏览器提供，不能作为安全判断唯一依据。
    with pytest.raises(UploadAnalysisError, match="不一致"):
        validate_upload_content(b"not an image", "image/png")


def test_user_material_context_preserves_source_and_limitations() -> None:
    """上传观察进入 Agent 前必须带输入 ID 和不可作为比赛事实的限制。"""
    # 该测试不调用真实视觉模型，只验证后续 Agent 实际接收的安全文本结构。
    evidence = VisualEvidence(
        input_id="visual-123",
        observations=["图中可见四后卫横向站位。"],
        confidence=0.55,
        limitations=["截图不包含完整比赛时间线。"],
    )
    context = build_user_material_context(evidence, "tactics.png")
    assert "visual-123" in context
    assert "截图不包含完整比赛时间线" in context
    assert "不得单独当作已核验比赛事实" in context

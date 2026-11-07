"""验证视觉模型结构化输出的校验与安全降级。"""

from __future__ import annotations

from multimodal.evidence_context import build_user_material_context
from multimodal.vision_service import parse_structured_visual_observation


def test_structured_visual_json_becomes_typed_evidence() -> None:
    """合规 JSON 应保留可见阵型、箭头和不确定项，而不是变成一段不可评测文本。"""
    # 不调用真实视觉模型，直接验证其返回内容进入 Agent 前的契约。
    evidence = parse_structured_visual_observation(
        "visual-456",
        '{"observations":["图中可见四名后卫横向站位。"],"formation":"4后卫","visible_player_count":4,"directional_arrows":["左路向前"],"pitch_zones":["左侧肋部"],"visible_labels":["Press"],"confidence":0.7,"limitations":["右侧被遮挡"]}',
    )
    assert evidence.formation == "4后卫"
    assert evidence.visible_player_count == 4
    assert evidence.directional_arrows == ["左路向前"]
    assert "真实比赛事实" in evidence.limitations[-1]
    assert "可见阵型：4后卫" in build_user_material_context(evidence, "board.png")


def test_invalid_visual_json_degrades_without_inventing_structure() -> None:
    """模型不遵守 JSON 格式时，系统应降低置信度且不伪造阵型字段。"""
    # 降级比直接报错更适合用户上传场景，但必须明确其不能作为强证据。
    evidence = parse_structured_visual_observation("visual-789", "这是一段没有 JSON 格式的描述")
    assert evidence.formation is None
    assert evidence.confidence == 0.3
    assert any("未返回可校验" in item for item in evidence.limitations)

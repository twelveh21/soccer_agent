"""把上传材料的解析结果转换为 Agent 可安全消费的用户证据上下文。"""

from __future__ import annotations

from typing import Any

from multimodal.contracts import VisualEvidence


def build_user_material_context(
    evidence: VisualEvidence | dict[str, Any],
    filename: str,
    max_characters: int = 2_000,
) -> str:
    """把视觉或文本观察压缩为带边界提示的用户材料上下文。

    参数：evidence 是上传解析结果；filename 是原始文件名；max_characters 限制进入研究提示词的最长文本。
    实现：提取 input_id、观察和局限，截断过长观察，并明确要求 Agent 将其视作未核验用户材料。
    """
    payload = evidence.model_dump() if isinstance(evidence, VisualEvidence) else evidence
    observations = [str(item).strip() for item in payload.get("observations", []) if str(item).strip()]
    limitations = [str(item).strip() for item in payload.get("limitations", []) if str(item).strip()]
    observation_text = "\n".join(f"- {item}" for item in observations)[:max_characters]
    limitation_text = "\n".join(f"- {item}" for item in limitations) or "- 该材料尚未经过外部来源核验。"
    structure_lines = [
        f"- 可见阵型：{payload['formation']}" if payload.get("formation") else "",
        f"- 可见人数：{payload['visible_player_count']}" if payload.get("visible_player_count") is not None else "",
        f"- 可见箭头：{'；'.join(map(str, payload.get('directional_arrows', [])))}" if payload.get("directional_arrows") else "",
        f"- 可见场地区域：{'；'.join(map(str, payload.get('pitch_zones', [])))}" if payload.get("pitch_zones") else "",
    ]
    structure_text = "\n".join(item for item in structure_lines if item)
    return (
        f"【用户上传材料】\n"
        f"- 文件：{filename}\n"
        f"- 输入 ID：{payload.get('input_id', 'unknown')}\n"
        f"- 可见/提取内容：\n{observation_text or '- 未提取到可用内容。'}\n"
        f"{f'- 结构化观察：\\n{structure_text}\\n' if structure_text else ''}"
        f"- 使用限制：\n{limitation_text}\n"
        "- 仅可将以上内容表述为‘用户材料中可见/可读’，不得单独当作已核验比赛事实。"
    )

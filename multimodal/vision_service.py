"""上传材料的安全解析与视觉观察服务。"""

from __future__ import annotations

import base64
import json
import os
import re
from io import BytesIO
from pathlib import Path

import httpx
from pypdf import PdfReader

from multimodal.contracts import StructuredVisualObservation, VisualEvidence, VisualInput

IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
TEXT_TYPES = {"text/plain", "text/markdown", "application/pdf"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


class UploadAnalysisError(Exception):
    """上传内容不安全、格式不支持或视觉模型不可用时抛出。"""


def validate_upload_content(content: bytes, content_type: str) -> None:
    """检查上传文件的实际文件头是否符合声明 MIME 类型。

    参数：content 是上传的原始字节；content_type 是 HTTP 请求中声明的文件类型。
    实现：图片和 PDF 检查常见 magic bytes；纯文本保持 UTF-8 宽松解码，避免只相信浏览器提交的 content_type。
    """
    signatures = {
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/jpeg": b"\xff\xd8\xff",
        "image/webp": b"RIFF",
        "application/pdf": b"%PDF-",
    }
    if content_type == "image/webp":
        if not (content.startswith(signatures[content_type]) and content[8:12] == b"WEBP"):
            raise UploadAnalysisError("上传内容与声明的 WebP 类型不一致。")
        return
    if content_type in signatures and not content.startswith(signatures[content_type]):
        raise UploadAnalysisError("上传内容与声明的文件类型不一致。")
    if content_type in {"text/plain", "text/markdown"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise UploadAnalysisError("文本材料必须使用 UTF-8 编码。") from error


def extract_text_content(content: bytes, content_type: str) -> str:
    """从 txt、md 或 PDF 提取有限长度文本，避免把完整文件塞进模型上下文。"""
    # 文本和 PDF 只抽取前 12,000 字符，原文件仍仅保存在受控 uploads 目录。
    if content_type in {"text/plain", "text/markdown"}:
        return content.decode("utf-8", errors="replace")[:12000]
    if content_type == "application/pdf":
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)[:12000]
    raise UploadAnalysisError("当前只支持 PNG、JPG、WebP、TXT、Markdown 和 PDF。")


def parse_structured_visual_observation(input_id: str, model_text: str) -> VisualEvidence:
    """把视觉模型 JSON 文本校验为结构化证据，失败时保守降级。

    参数：input_id 是上传材料标识；model_text 是视觉模型返回的原始文本。
    实现：先移除 Markdown 代码围栏并解析 JSON；字段通过 Pydantic 校验后写入 VisualEvidence，无法解析时仅保留原文观察和明确局限。
    """
    normalized = re.sub(r"^```(?:json)?\s*|\s*```$", "", model_text.strip(), flags=re.IGNORECASE)
    try:
        payload = StructuredVisualObservation.model_validate(json.loads(normalized))
    except (json.JSONDecodeError, ValueError):
        return VisualEvidence(
            input_id=input_id,
            observations=[model_text[:1_500]],
            confidence=0.3,
            limitations=[
                "视觉模型未返回可校验的结构化结果，以下仅保留原始观察文本。",
                "视觉结果仅表示上传材料中的可见信息，不能单独证明真实比赛事实。",
            ],
        )
    return VisualEvidence(
        input_id=input_id,
        observations=payload.observations,
        confidence=payload.confidence,
        limitations=[
            *payload.limitations,
            "视觉结果仅表示上传材料中的可见信息，不能单独证明真实比赛事实。",
        ],
        formation=payload.formation,
        visible_player_count=payload.visible_player_count,
        directional_arrows=payload.directional_arrows,
        pitch_zones=payload.pitch_zones,
        visible_labels=payload.visible_labels,
    )


async def analyze_image(input_item: VisualInput, content: bytes, content_type: str) -> VisualEvidence:
    """使用兼容 OpenAI 的视觉模型提取可审阅观察，而非直接生成比赛结论。"""
    # 模型只被要求描述图中可见内容；最终 Agent 仍须把它当成带局限的用户材料。
    base_url = os.getenv("DASHSCOPE_BASE_URL", "").rstrip("/")
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not base_url or not api_key:
        raise UploadAnalysisError("未配置视觉模型所需的 DASHSCOPE_BASE_URL 或 DASHSCOPE_API_KEY。")
    image_url = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
    request_body = {
        "model": os.getenv("SOCCER_AGENT_VISION_MODEL", "qwen-vl-plus"),
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "你是足球视觉材料助手。只描述图片可见的阵型、站位、箭头、文字或比赛画面，不要编造比分、球员身份或战术结论。必须只输出一个 JSON 对象，不要 Markdown。格式：{\"observations\":[\"最多6条可见观察\"],\"formation\":\"可见阵型或null\",\"visible_player_count\":可见人数或null,\"directional_arrows\":[\"箭头方向/含义，仅限可见\"],\"pitch_zones\":[\"可见区域\"],\"visible_labels\":[\"图中文字\"],\"confidence\":0到1,\"limitations\":[\"模糊、遮挡或缺失信息\"]}。"},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]}],
        "temperature": 0.1,
    }
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.post(f"{base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json=request_body)
        response.raise_for_status()
        content_text = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as error:
        raise UploadAnalysisError("视觉模型暂时无法分析该图片，请检查视觉模型名称与账户权限。") from error
    return parse_structured_visual_observation(input_item.input_id, content_text)

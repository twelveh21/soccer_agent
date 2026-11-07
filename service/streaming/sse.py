"""SSE 编码工具：将安全事件转换为浏览器可消费的文本帧。"""

from __future__ import annotations

import json

from service.streaming.events import ResearchStreamEvent


def encode_sse(event: ResearchStreamEvent) -> str:
    """把受 Pydantic 约束的事件编码成一条 SSE 消息。"""
    # 使用 JSON 避免换行和特殊字符破坏 SSE 帧；事件内容不含 Prompt、密钥或网页原文。
    return f"event: {event.event}\ndata: {event.model_dump_json()}\n\n"

"""权威公开战术资料源注册表，避免无约束抓取网络文章。"""

from __future__ import annotations

import json
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name("authoritative_sources.json")


def list_authoritative_sources() -> list[dict[str, object]]:
    """返回可展示、可审查的战术资料源元数据，不复制原站文章正文。"""
    # 原站内容仍通过 URL 访问；本项目只维护主题、用途和出处，以尊重版权与更新边界。
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def build_authoritative_tactics_query(question: str) -> str:
    """把研究问题限定到已审核的公开战术资料域名。"""
    # 域名约束降低低质量转载内容进入战术研究证据链的概率。
    return f"({question}) (site:fifatrainingcentre.com OR site:learning.coachesvoice.com)"

"""将人工维护的战术基础条目校验、切块并构造成可检索的本地索引。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FOUNDATIONS_PATH = PROJECT_ROOT / "knowledge_base" / "seed" / "tactical_foundations.json"
INDEX_PATH = PROJECT_ROOT / "knowledge_base" / "indexes" / "tactical_foundation_chunks.json"


class TacticalFoundation(BaseModel):
    """一条人工维护的稳定战术概念资料。"""

    # id 是长期稳定的引用键；body 是可切块正文；limitations 防止概念被误用为比赛事实。
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=4)
    tags: list[str] = Field(min_length=1)
    summary: str = Field(min_length=8)
    body: str = Field(min_length=30)
    limitations: str = Field(min_length=8)


class TacticalChunk(BaseModel):
    """检索器实际打分的最小文本单元。"""

    # document_id 用来回溯完整概念；ordinal 保留正文中的顺序，方便未来扩展到文章级引用定位。
    chunk_id: str
    document_id: str
    title: str
    tags: list[str]
    text: str
    summary: str
    limitations: str
    ordinal: int = Field(ge=0)


def load_foundations(path: Path = FOUNDATIONS_PATH) -> list[TacticalFoundation]:
    """读取并逐条校验基础知识，尽早发现格式不完整或重复的资料。"""
    # 在入库阶段失败比在用户提问时才报错更容易定位，也避免坏条目污染检索结果。
    with path.open("r", encoding="utf-8") as file:
        raw_items = json.load(file)
    if not isinstance(raw_items, list):
        raise ValueError("战术基础资料必须是 JSON 列表。")
    foundations = [TacticalFoundation.model_validate(item) for item in raw_items]
    ids = [item.id for item in foundations]
    if len(ids) != len(set(ids)):
        raise ValueError("战术基础资料中存在重复 id。")
    return foundations


def split_into_chunks(text: str, max_characters: int = 260) -> list[str]:
    """按中文句子边界将正文切为大小受控的检索片段。"""
    # 先按句号、问号和分号切分，尽量保持完整语义；只有超长句才按字符兜底切分。
    sentences = [segment.strip() for segment in re.split(r"(?<=[。！？；])", text) if segment.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_characters:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                sentence[index:index + max_characters]
                for index in range(0, len(sentence), max_characters)
            )
            continue
        if current and len(current) + len(sentence) > max_characters:
            chunks.append(current)
            current = sentence
        else:
            current += sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def build_foundation_chunks(foundations: list[TacticalFoundation]) -> list[TacticalChunk]:
    """将每条概念资料转换为一个或多个带引用信息的检索块。"""
    # 检索块保留完整标题与限制，保证即使单独命中一段文字也能被正确解释和引用。
    chunks: list[TacticalChunk] = []
    for foundation in foundations:
        for ordinal, text in enumerate(split_into_chunks(foundation.body)):
            chunks.append(
                TacticalChunk(
                    chunk_id=f"{foundation.id}#{ordinal}",
                    document_id=foundation.id,
                    title=foundation.title,
                    tags=foundation.tags,
                    text=text,
                    summary=foundation.summary,
                    limitations=foundation.limitations,
                    ordinal=ordinal,
                )
            )
    return chunks


def write_foundation_index(
    chunks: list[TacticalChunk],
    path: Path = INDEX_PATH,
) -> Path:
    """把已校验切块写为版本化本地索引，供运行时快速加载。"""
    # 索引可由源资料重复生成，因此它是派生文件；真正应人工维护的是 seed 下的原始知识条目。
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source": "knowledge_base/seed/tactical_foundations.json",
        "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_and_write_foundation_index() -> Path:
    """执行完整本地导入流程：读取源资料、校验、切块并写出索引。"""
    # 该函数是未来 CLI、CI 与知识维护脚本的唯一入口，避免三处重复实现导入流程。
    return write_foundation_index(build_foundation_chunks(load_foundations()))

"""本地战术知识库的透明混合检索：标签、标题和正文按不同权重共同评分。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from knowledge_base.ingestion.foundation_ingestion import INDEX_PATH, TacticalChunk, build_and_write_foundation_index


def normalize_text(value: str) -> str:
    """统一小写、空白与连字符，减少中英文术语书写差异造成的漏检。"""
    # 不做激进的中文分词或同义词猜测，保证当前小型知识库的匹配逻辑可读可调试。
    return re.sub(r"\s+", " ", value.lower().replace("-", " ")).strip()


def extract_query_terms(query: str, chunks: tuple[TacticalChunk, ...]) -> set[str]:
    """从查询中找出知识库已知标签，并保留英文短语作为补充。"""
    # 使用知识库自身标签作为词表，新增知识条目后无需手动同步另一份固定 vocabulary。
    normalized_query = normalize_text(query)
    tags = {normalize_text(tag) for chunk in chunks for tag in chunk.tags}
    terms = {tag for tag in tags if tag and tag in normalized_query}
    terms.update(word.strip() for word in re.findall(r"[a-z][a-z ]{2,}", normalized_query) if word.strip())
    return terms


@lru_cache(maxsize=1)
def load_indexed_chunks() -> tuple[TacticalChunk, ...]:
    """加载切块索引；首次使用且索引缺失时自动从源资料构建。"""
    # 自动构建让首次克隆项目也能运行，索引存在时则不在每次问题中重复进行导入工作。
    if not INDEX_PATH.exists():
        build_and_write_foundation_index()
    with INDEX_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if payload.get("schema_version") != 1:
        raise ValueError("当前本地战术索引版本不受支持，请重新构建索引。")
    return tuple(TacticalChunk.model_validate(item) for item in payload.get("chunks", []))


def score_chunk(chunk: TacticalChunk, terms: set[str]) -> int:
    """根据命中位置计算可解释的混合检索分数。"""
    # 标签是作者显式赋予的概念，权重最高；标题其次；正文匹配用于捕捉相近但未标成标签的表达。
    title = normalize_text(chunk.title)
    tags = {normalize_text(tag) for tag in chunk.tags}
    body = normalize_text(chunk.text)
    return sum(5 for term in terms if term in tags) + sum(3 for term in terms if term in title) + sum(
        1 for term in terms if term in body
    )


def retrieve_hybrid(query: str, top_k: int = 4) -> list[tuple[int, TacticalChunk]]:
    """返回分数大于零的最相关切块，供上层包装为统一证据。"""
    # 当没有直接概念命中时返回空，宁可让 Critic 看见证据缺口，也不把无关笔记强塞进 Solver。
    if top_k < 1:
        raise ValueError("top_k 必须至少为 1。")
    chunks = load_indexed_chunks()
    terms = extract_query_terms(query, chunks)
    ranked = sorted(((score_chunk(chunk, terms), chunk) for chunk in chunks), key=lambda pair: pair[0], reverse=True)
    return [(score, chunk) for score, chunk in ranked[:top_k] if score > 0]

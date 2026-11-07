"""验证本地战术基础资料在入库前可被校验、切块和重建索引。"""

from __future__ import annotations

from knowledge_base.ingestion.foundation_ingestion import (
    build_foundation_chunks,
    load_foundations,
    split_into_chunks,
)


def test_foundations_have_unique_ids_and_become_chunks() -> None:
    """每条源资料都应产生至少一个可被检索的切块。"""
    # 防止编辑 seed 文件时出现重复 id 或正文为空导致资料静默丢失。
    foundations = load_foundations()
    chunks = build_foundation_chunks(foundations)
    assert len({item.id for item in foundations}) == len(foundations)
    assert {chunk.document_id for chunk in chunks} == {item.id for item in foundations}


def test_sentence_chunking_respects_max_length() -> None:
    """切块应尽量保持句子完整，同时不会产生超长普通片段。"""
    # 使用短句组合模拟战术文章，确保切块逻辑可在未来文章级导入中复用。
    chunks = split_into_chunks("第一句。第二句。第三句。", max_characters=7)
    assert chunks == ["第一句。", "第二句。", "第三句。"]

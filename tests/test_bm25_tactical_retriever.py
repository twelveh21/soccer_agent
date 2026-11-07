"""验证 BM25 战术检索的排序、引用和无关问题边界。"""

from __future__ import annotations

from knowledge_base.retrieval.bm25_tactical_retriever import retrieve_with_bm25


def test_bm25_returns_citable_pressing_passage() -> None:
    """高位压迫问题应命中压迫知识块，并保留后续回答需要的引用信息。"""
    # 该用例不调用模型或网络，确保 CI 能稳定发现检索逻辑回归。
    passages = retrieve_with_bm25("高位压迫怎样封锁中场传球线路", top_k=2)
    assert passages
    assert passages[0].citation_id.startswith("local-foundation:pressing-and-counterpress#")
    assert passages[0].metadata["retrieval_method"] == "bm25"


def test_bm25_does_not_force_an_irrelevant_result() -> None:
    """完全无关的问题应返回空，不能为了看似有答案而输出战术资料。"""
    # 空结果会成为 Critic 的“资料不足”信号，而不是被 Solver 误认为有证据。
    assert retrieve_with_bm25("火星殖民基地的能源供应", top_k=2) == []

"""验证向量通道与 RRF 融合的战术检索契约。"""

from __future__ import annotations

from knowledge_base.retrieval.advanced_tactical_retriever import retrieve_advanced_tactical_knowledge
from knowledge_base.retrieval.bm25_tactical_retriever import retrieve_with_bm25
from knowledge_base.retrieval.rrf import reciprocal_rank_fusion
from knowledge_base.retrieval.vector_tactical_retriever import retrieve_with_sparse_vector


def test_advanced_retriever_returns_fused_citable_passages() -> None:
    """融合入口应输出证据片段、稳定引用和融合来源信息。"""
    # 此测试确保将来替换真实 embedding 服务时，上层 Agent 的引用契约不会变化。
    passages = retrieve_advanced_tactical_knowledge("高位压迫与反抢如何限制向前传球", top_k=2)
    assert passages
    assert passages[0].citation_id.startswith("local-foundation:")
    assert passages[0].metadata["retrieval_method"] == "lightweight_reranker"
    assert passages[0].metadata["reranked_from"] == "rrf_fusion"


def test_rrf_deduplicates_the_same_citation_from_two_channels() -> None:
    """同一资料同时被 BM25 和向量命中时，RRF 应合并而不是重复返回。"""
    # 重复证据会浪费 Solver 上下文，也会让同一来源在回答中被误认为多份独立资料。
    bm25 = retrieve_with_bm25("高位压迫", top_k=2)
    vector = retrieve_with_sparse_vector("高位压迫", top_k=2)
    fused = reciprocal_rank_fusion([bm25, vector], top_k=4)
    assert len({passage.citation_id for passage in fused}) == len(fused)

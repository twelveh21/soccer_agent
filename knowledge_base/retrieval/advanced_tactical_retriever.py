"""组合 BM25 与本地向量通道的高级战术检索入口。"""

from __future__ import annotations

from knowledge_base.retrieval.bm25_tactical_retriever import retrieve_with_bm25
from knowledge_base.retrieval.contracts import RetrievedPassage
from knowledge_base.retrieval.reranker import rerank_passages
from knowledge_base.retrieval.rrf import reciprocal_rank_fusion
from knowledge_base.retrieval.vector_tactical_retriever import retrieve_with_sparse_vector


def retrieve_advanced_tactical_knowledge(query: str, top_k: int = 4) -> list[RetrievedPassage]:
    """同时运行 BM25 与向量检索，并用 RRF 返回融合后的可引用证据。

    参数：query 是用户战术问题；top_k 是最终供 Solver 阅读的片段数。
    实现：每条通道多取少量候选以提高召回率，RRF 再合并相同引用并挑选最终靠前结果。
    """
    candidate_limit = min(top_k * 2, 20)
    bm25_passages = retrieve_with_bm25(query, top_k=candidate_limit)
    vector_passages = retrieve_with_sparse_vector(query, top_k=candidate_limit)
    fused_passages = reciprocal_rank_fusion([bm25_passages, vector_passages], top_k=candidate_limit)
    return rerank_passages(query, fused_passages, top_k=top_k)
